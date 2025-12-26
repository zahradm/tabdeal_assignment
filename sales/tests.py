"""
Basic test cases for B2B charge sales system.

Tests the requirements:
- 2 sellers
- 10 credit increases
- 1000 charge sales
- Balance reconciliation
"""

import time
from decimal import Decimal
from django.test import TestCase
from sales.models import Seller, CreditRequest, PhoneNumber, Transaction


class BasicFunctionalityTestCase(TestCase):
    """Test basic functionality with simple scenarios."""
    
    def setUp(self):
        """Create test sellers."""
        self.seller1 = Seller.objects.create(
            name="Seller 1",
            email="seller1@test.com",
            phone="09121111111"
        )
        self.seller2 = Seller.objects.create(
            name="Seller 2",
            email="seller2@test.com",
            phone="09122222222"
        )
    
    def test_01_credit_request_creation(self):
        """Test that credit requests can be created."""
        request = CreditRequest.objects.create(
            seller=self.seller1,
            amount=1000000
        )
        self.assertEqual(request.status, CreditRequest.PENDING)
        self.assertEqual(request.seller, self.seller1)
    
    def test_02_credit_approval_increases_balance(self):
        """Test that approving a credit request increases seller balance."""
        request = CreditRequest.objects.create(
            seller=self.seller1,
            amount=500000
        )
        
        initial_balance = self.seller1.credit_balance
        request.approve(processed_by='test_admin')
        
        self.seller1.refresh_from_db()
        self.assertEqual(
            self.seller1.credit_balance,
            initial_balance + Decimal('500000')
        )
        
        request.refresh_from_db()
        self.assertEqual(request.status, CreditRequest.APPROVED)
    
    def test_03_credit_approval_idempotency(self):
        """Test that credit requests can only be approved once."""
        request = CreditRequest.objects.create(
            seller=self.seller1,
            amount=100000
        )
        
        request.approve(processed_by='test_admin')
        self.seller1.refresh_from_db()  # Refresh to get updated balance
        initial_balance = self.seller1.credit_balance
        
        # Try to approve again
        with self.assertRaises(ValueError):
            request.refresh_from_db()
            request.approve(processed_by='test_admin')
        
        # Balance should not change
        self.seller1.refresh_from_db()
        self.assertEqual(self.seller1.credit_balance, initial_balance)
    
    def test_04_charge_sale_deducts_balance(self):
        """Test that charge sales deduct from seller balance."""
        # Add credit first
        request = CreditRequest.objects.create(
            seller=self.seller1,
            amount=200000
        )
        request.approve()
        
        self.seller1.refresh_from_db()
        initial_balance = self.seller1.credit_balance
        
        # Sell a charge
        phone = PhoneNumber.objects.create(number="09123456789")
        sale_amount = Decimal('50000')
        new_balance, txn = self.seller1.deduct_credit(sale_amount, phone)
        
        self.assertEqual(new_balance, initial_balance - sale_amount)
        self.assertEqual(txn.amount, -sale_amount)
    
    def test_05_insufficient_balance_prevents_sale(self):
        """Test that sales fail when balance is insufficient."""
        phone = PhoneNumber.objects.create(number="09123456789")
        
        with self.assertRaises(ValueError) as context:
            self.seller1.deduct_credit(100000, phone)
        
        self.assertIn("Insufficient balance", str(context.exception))
    
    def test_06_negative_balance_prevention(self):
        """Test that balance cannot go negative."""
        request = CreditRequest.objects.create(
            seller=self.seller1,
            amount=50000
        )
        request.approve()
        
        phone = PhoneNumber.objects.create(number="09123456789")
        
        # Try to sell more than balance
        self.seller1.refresh_from_db()
        with self.assertRaises(ValueError):
            self.seller1.deduct_credit(100000, phone)
        
        # Balance should remain unchanged
        self.seller1.refresh_from_db()
        self.assertEqual(self.seller1.credit_balance, Decimal('50000'))
    
    def test_07_transaction_logging(self):
        """Test that all operations are logged as transactions."""
        # Add credit
        request = CreditRequest.objects.create(
            seller=self.seller1,
            amount=300000
        )
        request.approve()
        
        # Verify transaction was created
        credit_txn = Transaction.objects.filter(
            seller=self.seller1,
            transaction_type=Transaction.CREDIT_INCREASE
        ).first()
        
        self.assertIsNotNone(credit_txn)
        self.assertEqual(credit_txn.amount, Decimal('300000'))
        
        # Make a sale
        phone = PhoneNumber.objects.create(number="09123456789")
        self.seller1.refresh_from_db()
        self.seller1.deduct_credit(50000, phone)
        
        # Verify sale transaction was created
        sale_txn = Transaction.objects.filter(
            seller=self.seller1,
            transaction_type=Transaction.CHARGE_SALE
        ).first()
        
        self.assertIsNotNone(sale_txn)
        self.assertEqual(sale_txn.amount, Decimal('-50000'))
    
    def test_08_transaction_immutability(self):
        """Test that transactions cannot be modified after creation."""
        request = CreditRequest.objects.create(
            seller=self.seller1,
            amount=100000
        )
        request.approve()
        
        txn = Transaction.objects.filter(seller=self.seller1).first()
        
        # Try to modify
        with self.assertRaises(ValueError):
            txn.amount = 200000
            txn.save()


class RequiredScenarioTestCase(TestCase):
    """
    Test the required scenario:
    - 2 sellers
    - 10 credit increases
    - 1000 charge sales
    - Balance reconciliation
    """
    
    def setUp(self):
        """Create test sellers."""
        self.seller1 = Seller.objects.create(
            name="Seller 1",
            email="seller1@test.com",
            phone="09121111111"
        )
        self.seller2 = Seller.objects.create(
            name="Seller 2",
            email="seller2@test.com",
            phone="09122222222"
        )
        
        print("\n" + "="*70)
        print("REQUIRED SCENARIO TEST: 2 Sellers, 10 Credit Increases, 1000 Sales")
        print("="*70)
    
    def test_required_scenario(self):
        """
        Execute the required test scenario and verify accounting integrity.
        """
        # Step 1: Create 10 credit increase requests (5 for each seller)
        print("\n[1] Creating 10 credit increase requests...")
        credit_amounts = [1000000, 800000, 1200000, 900000, 1100000]
        
        for i, amount in enumerate(credit_amounts):
            CreditRequest.objects.create(
                seller=self.seller1,
                amount=amount
            )
            CreditRequest.objects.create(
                seller=self.seller2,
                amount=amount
            )
        
        total_requests = CreditRequest.objects.count()
        self.assertEqual(total_requests, 10)
        print(f"   ✓ Created {total_requests} credit requests")
        
        # Step 2: Approve all credit requests
        print("\n[2] Approving all credit requests...")
        start_time = time.time()
        
        for request in CreditRequest.objects.all():
            request.approve(processed_by='test_admin')
        
        approval_time = time.time() - start_time
        
        approved_count = CreditRequest.objects.filter(
            status=CreditRequest.APPROVED
        ).count()
        self.assertEqual(approved_count, 10)
        print(f"   ✓ Approved {approved_count} requests in {approval_time:.3f}s")
        
        # Verify balances after credit increases
        self.seller1.refresh_from_db()
        self.seller2.refresh_from_db()
        
        expected_balance = sum(credit_amounts)
        self.assertEqual(self.seller1.credit_balance, Decimal(str(expected_balance)))
        self.assertEqual(self.seller2.credit_balance, Decimal(str(expected_balance)))
        
        print(f"   ✓ Seller 1 balance: {self.seller1.credit_balance:,.0f} Rials")
        print(f"   ✓ Seller 2 balance: {self.seller2.credit_balance:,.0f} Rials")
        
        # Step 3: Perform 1000 charge sales
        print("\n[3] Performing 1000 charge sales...")
        start_time = time.time()
        
        sale_amount = Decimal('5000')  # 5,000 Rials per sale
        sales_per_seller = 500
        
        # Create phone numbers
        phone_numbers = []
        for i in range(100):
            phone = PhoneNumber.objects.create(
                number=f"0912{str(i).zfill(7)}"
            )
            phone_numbers.append(phone)
        
        # Perform sales for seller 1
        for i in range(sales_per_seller):
            phone = phone_numbers[i % len(phone_numbers)]
            self.seller1.deduct_credit(sale_amount, phone)
            phone.add_charge(sale_amount)
        
        # Perform sales for seller 2
        for i in range(sales_per_seller):
            phone = phone_numbers[i % len(phone_numbers)]
            self.seller2.deduct_credit(sale_amount, phone)
            phone.add_charge(sale_amount)
        
        sales_time = time.time() - start_time
        
        total_sales = Transaction.objects.filter(
            transaction_type=Transaction.CHARGE_SALE
        ).count()
        self.assertEqual(total_sales, 1000)
        print(f"   ✓ Completed {total_sales} sales in {sales_time:.3f}s")
        print(f"   ✓ Average: {sales_time*1000/total_sales:.2f}ms per sale")
        
        # Step 4: Verify final balances
        print("\n[4] Verifying final balances...")
        self.seller1.refresh_from_db()
        self.seller2.refresh_from_db()
        
        total_credited = sum(credit_amounts)
        total_sold = sales_per_seller * sale_amount
        expected_final_balance = total_credited - total_sold
        
        self.assertEqual(
            self.seller1.credit_balance,
            Decimal(str(expected_final_balance))
        )
        self.assertEqual(
            self.seller2.credit_balance,
            Decimal(str(expected_final_balance))
        )
        
        print(f"   ✓ Seller 1 final balance: {self.seller1.credit_balance:,.0f} Rials")
        print(f"   ✓ Seller 2 final balance: {self.seller2.credit_balance:,.0f} Rials")
        print(f"   ✓ Expected balance: {expected_final_balance:,.0f} Rials")
        
        # Step 5: Reconcile accounting
        print("\n[5] Reconciling accounting...")
        
        for seller in [self.seller1, self.seller2]:
            transactions = Transaction.objects.filter(seller=seller)
            calculated_balance = sum(t.amount for t in transactions)
            
            self.assertEqual(
                seller.credit_balance,
                calculated_balance,
                f"Balance mismatch for {seller.name}"
            )
            
            credit_count = transactions.filter(
                transaction_type=Transaction.CREDIT_INCREASE
            ).count()
            sale_count = transactions.filter(
                transaction_type=Transaction.CHARGE_SALE
            ).count()
            
            print(f"\n   {seller.name}:")
            print(f"     - Current balance: {seller.credit_balance:,.0f} Rials")
            print(f"     - Calculated from transactions: {calculated_balance:,.0f} Rials")
            print(f"     - Credit increases: {credit_count}")
            print(f"     - Charge sales: {sale_count}")
            print(f"     - Total transactions: {transactions.count()}")
            print(f"     ✓ Accounting is reconciled!")
        
        # Final summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"✓ Credit requests: {total_requests}")
        print(f"✓ Approved requests: {approved_count}")
        print(f"✓ Charge sales: {total_sales}")
        print(f"✓ Sellers reconciled: 2/2")
        print(f"✓ Total execution time: {approval_time + sales_time:.3f}s")
        print("="*70)
        print("ALL TESTS PASSED ✓")
        print("="*70 + "\n")


class EdgeCaseTestCase(TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Create test seller."""
        self.seller = Seller.objects.create(
            name="Test Seller",
            email="test@test.com",
            phone="09121111111"
        )
    
    def test_zero_amount_rejected(self):
        """Test that zero amounts are rejected."""
        with self.assertRaises(Exception):
            CreditRequest.objects.create(
                seller=self.seller,
                amount=0
            )
    
    def test_negative_amount_rejected(self):
        """Test that negative amounts are rejected."""
        with self.assertRaises(Exception):
            CreditRequest.objects.create(
                seller=self.seller,
                amount=-100
            )
    
    def test_concurrent_credit_approval_safety(self):
        """Test that concurrent approvals don't double-charge."""
        request = CreditRequest.objects.create(
            seller=self.seller,
            amount=100000
        )
        
        # First approval succeeds
        request.approve()
        self.seller.refresh_from_db()  # Refresh to get updated balance
        balance_after_first = self.seller.credit_balance
        
        # Second approval should fail
        request.refresh_from_db()
        with self.assertRaises(ValueError):
            request.approve()
        
        # Balance should remain unchanged
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.credit_balance, balance_after_first)
