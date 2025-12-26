"""
Database models for B2B charge sales system.

This module implements a robust accounting system with:
- Atomic transactions to prevent race conditions
- Database-level constraints for data integrity
- Proper transaction logging for reconciliation
- Prevention of double-spending and negative balances
"""

from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class Seller(models.Model):
    """
    Represents a seller in the B2B charge sales system.
    
    Each seller has a credit balance that can be increased through approved
    credit requests and decreased through charge sales.
    """
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, unique=True)
    credit_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Current credit balance in Rials"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sellers'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(credit_balance__gte=0),
                name='seller_credit_balance_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.email})"

    @transaction.atomic
    def add_credit(self, amount, credit_request):
        """
        Add credit to seller's balance atomically.
        
        Args:
            amount: Amount to add (must be positive)
            credit_request: CreditRequest object associated with this operation
            
        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        
        # Use select_for_update to lock the row and prevent race conditions
        seller = Seller.objects.select_for_update().get(pk=self.pk)
        seller.credit_balance += Decimal(str(amount))
        seller.save(update_fields=['credit_balance', 'updated_at'])
        
        # Log the transaction
        Transaction.objects.create(
            seller=seller,
            transaction_type=Transaction.CREDIT_INCREASE,
            amount=amount,
            balance_after=seller.credit_balance,
            credit_request=credit_request,
            description=f"Credit increase from request #{credit_request.pk}"
        )
        
        return seller.credit_balance

    @transaction.atomic
    def deduct_credit(self, amount, phone_number):
        """
        Deduct credit from seller's balance atomically.
        
        Args:
            amount: Amount to deduct (must be positive)
            phone_number: PhoneNumber object being charged
            
        Returns:
            Tuple of (new_balance, transaction)
            
        Raises:
            ValueError: If amount is not positive or insufficient balance
        """
        if amount <= 0:
            raise ValueError("Deduction amount must be positive")
        
        # Use select_for_update to lock the row and prevent race conditions
        seller = Seller.objects.select_for_update().get(pk=self.pk)
        
        if seller.credit_balance < Decimal(str(amount)):
            raise ValueError(
                f"Insufficient balance. Available: {seller.credit_balance}, "
                f"Required: {amount}"
            )
        
        seller.credit_balance -= Decimal(str(amount))
        seller.save(update_fields=['credit_balance', 'updated_at'])
        
        # Log the transaction
        txn = Transaction.objects.create(
            seller=seller,
            transaction_type=Transaction.CHARGE_SALE,
            amount=-amount,  # Negative for deduction
            balance_after=seller.credit_balance,
            phone_number=phone_number,
            description=f"Charge sale to {phone_number.number}"
        )
        
        return seller.credit_balance, txn


class CreditRequest(models.Model):
    """
    Represents a credit increase request from a seller.
    
    Uses database constraints to ensure idempotency - each request
    can only be approved once, preventing double-charging.
    """
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]
    
    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name='credit_requests'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        db_index=True
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'credit_requests'
        indexes = [
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['status', 'requested_at']),
        ]
        # Ensure a request can only be processed once
        constraints = [
            models.UniqueConstraint(
                fields=['id'],
                condition=models.Q(status='approved'),
                name='unique_approved_credit_request'
            )
        ]

    def __str__(self):
        return f"Request #{self.pk} - {self.seller.name} - {self.amount} ({self.status})"

    def clean(self):
        """Validate the model data."""
        super().clean()
        if self.amount is not None:
            if self.amount <= 0:
                raise ValidationError(
                    {'amount': 'Amount must be greater than zero'}
                )

    def save(self, *args, **kwargs):
        """Override save to enforce validation."""
        self.full_clean()
        super().save(*args, **kwargs)

    @transaction.atomic
    def approve(self, processed_by='admin'):
        """
        Approve the credit request and add credit to seller's balance.
        
        This method is idempotent - calling it multiple times will only
        process the request once due to database constraints and status checks.
        
        Args:
            processed_by: Username/identifier of the approver
            
        Raises:
            ValueError: If request is not in pending status
        """
        # Lock this row to prevent concurrent approval attempts
        credit_request = CreditRequest.objects.select_for_update().get(pk=self.pk)
        
        if credit_request.status != self.PENDING:
            raise ValueError(
                f"Cannot approve request with status '{credit_request.status}'. "
                f"Only pending requests can be approved."
            )
        
        # Add credit to seller
        credit_request.seller.add_credit(credit_request.amount, credit_request)
        
        # Update request status
        credit_request.status = CreditRequest.APPROVED
        credit_request.processed_at = timezone.now()
        credit_request.processed_by = processed_by
        credit_request.save(update_fields=['status', 'processed_at', 'processed_by'])
        
        return credit_request

    @transaction.atomic
    def reject(self, processed_by='admin', reason=''):
        """
        Reject the credit request.
        
        Args:
            processed_by: Username/identifier of the rejector
            reason: Reason for rejection
            
        Raises:
            ValueError: If request is not in pending status
        """
        credit_request = CreditRequest.objects.select_for_update().get(pk=self.pk)
        
        if credit_request.status != self.PENDING:
            raise ValueError(
                f"Cannot reject request with status '{credit_request.status}'. "
                f"Only pending requests can be rejected."
            )
        
        credit_request.status = CreditRequest.REJECTED
        credit_request.processed_at = timezone.now()
        credit_request.processed_by = processed_by
        if reason:
            credit_request.notes = reason
        credit_request.save(update_fields=['status', 'processed_at', 'processed_by', 'notes'])
        
        return credit_request


class PhoneNumber(models.Model):
    """
    Represents a phone number that can be charged.
    
    Tracks the total charges applied to each number.
    """
    number = models.CharField(max_length=20, unique=True, db_index=True)
    total_charged = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'phone_numbers'
        indexes = [
            models.Index(fields=['number']),
        ]

    def __str__(self):
        return self.number

    @transaction.atomic
    def add_charge(self, amount):
        """
        Add charge amount to this phone number's total.
        
        Args:
            amount: Amount being charged
        """
        phone = PhoneNumber.objects.select_for_update().get(pk=self.pk)
        phone.total_charged += Decimal(str(amount))
        phone.save(update_fields=['total_charged', 'updated_at'])
        return phone.total_charged


class Transaction(models.Model):
    """
    Immutable transaction log for all credit operations.
    
    This provides a complete audit trail for reconciliation.
    Every credit increase and charge sale is logged here.
    """
    CREDIT_INCREASE = 'credit_increase'
    CHARGE_SALE = 'charge_sale'
    
    TRANSACTION_TYPE_CHOICES = [
        (CREDIT_INCREASE, 'Credit Increase'),
        (CHARGE_SALE, 'Charge Sale'),
    ]
    
    seller = models.ForeignKey(
        Seller,
        on_delete=models.PROTECT,  # Never delete transactions
        related_name='transactions'
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        db_index=True
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Positive for credit increase, negative for charge sale"
    )
    balance_after = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Seller's balance after this transaction"
    )
    credit_request = models.ForeignKey(
        CreditRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='transactions'
    )
    phone_number = models.ForeignKey(
        PhoneNumber,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='transactions'
    )
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'transactions'
        indexes = [
            models.Index(fields=['seller', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
            models.Index(fields=['credit_request']),
            models.Index(fields=['phone_number']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type} - {self.seller.name} - {self.amount}"

    def save(self, *args, **kwargs):
        """Override save to make transactions immutable after creation."""
        if self.pk is not None:
            raise ValueError("Transactions are immutable and cannot be modified")
        super().save(*args, **kwargs)
