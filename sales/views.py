"""
API views for B2B charge sales system.

Implements thread-safe and process-safe operations for:
- Charge sales (with race condition protection)
- Credit request management
- Transaction history
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Seller, CreditRequest, PhoneNumber, Transaction
from .serializers import (
    SellerSerializer,
    CreditRequestSerializer,
    CreditRequestApprovalSerializer,
    ChargeSaleSerializer,
    TransactionSerializer,
    PhoneNumberSerializer
)


class SellerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing sellers.
    """
    queryset = Seller.objects.all()
    serializer_class = SellerSerializer
    
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get current balance for a seller."""
        seller = self.get_object()
        return Response({
            'seller_id': seller.id,
            'name': seller.name,
            'credit_balance': seller.credit_balance
        })
    
    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """Get transaction history for a seller."""
        seller = self.get_object()
        transactions = seller.transactions.all()
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def reconcile(self, request, pk=None):
        """
        Reconcile seller's balance against transaction history.
        
        This verifies accounting integrity by summing all transactions
        and comparing with the current balance.
        """
        seller = self.get_object()
        
        # Sum all transactions
        transactions = Transaction.objects.filter(seller=seller)
        total_from_transactions = sum(
            t.amount for t in transactions
        )
        
        # Current balance should match transaction sum
        is_reconciled = seller.credit_balance == total_from_transactions
        
        return Response({
            'seller_id': seller.id,
            'name': seller.name,
            'current_balance': seller.credit_balance,
            'calculated_from_transactions': total_from_transactions,
            'is_reconciled': is_reconciled,
            'difference': seller.credit_balance - total_from_transactions,
            'total_transactions': transactions.count()
        })


class CreditRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing credit requests.
    """
    queryset = CreditRequest.objects.all()
    serializer_class = CreditRequestSerializer
    
    def get_queryset(self):
        """Filter by status if provided."""
        queryset = CreditRequest.objects.select_related('seller')
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """
        Approve or reject a credit request.
        
        This operation is idempotent - calling it multiple times will not
        result in duplicate credit additions.
        """
        credit_request = self.get_object()
        serializer = CreditRequestApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action_type = serializer.validated_data['action']
        processed_by = serializer.validated_data.get('processed_by', 'admin')
        reason = serializer.validated_data.get('reason', '')
        
        try:
            if action_type == 'approve':
                credit_request.approve(processed_by=processed_by)
                message = f"Credit request approved. New balance: {credit_request.seller.credit_balance}"
            else:
                credit_request.reject(processed_by=processed_by, reason=reason)
                message = "Credit request rejected"
            
            return Response({
                'status': 'success',
                'message': message,
                'credit_request': CreditRequestSerializer(credit_request).data
            })
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChargeSaleViewSet(viewsets.ViewSet):
    """
    ViewSet for charge sale operations.
    
    This is the core API for selling charges. It implements:
    - Atomic transactions to prevent race conditions
    - Balance validation to prevent negative balances
    - Proper transaction logging for accounting
    """
    
    @transaction.atomic
    def create(self, request):
        """
        Sell a charge to a phone number.
        
        POST /api/charge-sales/
        {
            "seller_id": 1,
            "phone_number": "09123456789",
            "amount": 50000
        }
        
        This operation is atomic and thread-safe. Multiple concurrent requests
        will be serialized by database locks to prevent race conditions.
        """
        serializer = ChargeSaleSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        seller_id = serializer.validated_data['seller_id']
        phone_number = serializer.validated_data['phone_number']
        amount = serializer.validated_data['amount']
        
        try:
            # Get or create phone number
            phone_obj, created = PhoneNumber.objects.get_or_create(
                number=phone_number
            )
            
            # Get seller with row lock to prevent concurrent modifications
            seller = Seller.objects.select_for_update().get(pk=seller_id)
            
            # Check if seller has sufficient balance
            if seller.credit_balance < amount:
                return Response(
                    {
                        'error': 'Insufficient balance',
                        'available_balance': str(seller.credit_balance),
                        'required_amount': str(amount),
                        'shortage': str(amount - seller.credit_balance)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Perform the charge sale (deduct from seller, log transaction)
            new_balance, txn = seller.deduct_credit(amount, phone_obj)
            
            # Update phone number total
            phone_obj.add_charge(amount)
            
            return Response({
                'status': 'success',
                'message': 'Charge sale completed',
                'transaction_id': txn.id,
                'seller_id': seller.id,
                'phone_number': phone_number,
                'amount': str(amount),
                'new_balance': str(new_balance)
            }, status=status.HTTP_201_CREATED)
            
        except Seller.DoesNotExist:
            return Response(
                {'error': 'Seller not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for viewing transaction history.
    
    Transactions are immutable and can only be created through
    credit approvals and charge sales.
    """
    queryset = Transaction.objects.select_related(
        'seller', 'credit_request', 'phone_number'
    )
    serializer_class = TransactionSerializer
    
    def get_queryset(self):
        """Filter by seller or transaction type if provided."""
        queryset = super().get_queryset()
        
        seller_id = self.request.query_params.get('seller_id', None)
        if seller_id:
            queryset = queryset.filter(seller_id=seller_id)
        
        transaction_type = self.request.query_params.get('type', None)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        return queryset


class PhoneNumberViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for viewing phone numbers and their charge history.
    """
    queryset = PhoneNumber.objects.all()
    serializer_class = PhoneNumberSerializer
    
    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """Get all charge transactions for this phone number."""
        phone = self.get_object()
        transactions = phone.transactions.all()
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)
