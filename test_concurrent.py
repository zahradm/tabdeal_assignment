"""
Concurrent and parallel load tests for B2B charge sales system.

Tests the system under heavy concurrent load using:
- Multithreading (threads share memory, GIL affects execution)
- Multiprocessing (separate processes, true parallelism)

This demonstrates understanding of the differences between multi-threading
and multi-processing in Python, especially regarding the GIL.
"""

import time
import random
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import django
import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction, connection
from sales.models import Seller, CreditRequest, PhoneNumber, Transaction


class ConcurrentTestRunner:
    """Runner for concurrent tests with both threading and multiprocessing."""
    
    def __init__(self):
        self.results = {
            'threading': {},
            'multiprocessing': {}
        }
    
    def setup_test_data(self):
        """Create initial test data."""
        print("\n" + "="*70)
        print("SETTING UP TEST DATA")
        print("="*70)
        
        # Clean existing data
        Transaction.objects.all().delete()
        PhoneNumber.objects.all().delete()
        CreditRequest.objects.all().delete()
        Seller.objects.all().delete()
        
        # Create sellers
        sellers = []
        for i in range(5):
            seller = Seller.objects.create(
                name=f"Seller {i+1}",
                email=f"seller{i+1}@test.com",
                phone=f"0912000{str(i+1).zfill(4)}"
            )
            sellers.append(seller)
        
        # Create and approve credit requests for each seller
        for seller in sellers:
            for j in range(3):
                request = CreditRequest.objects.create(
                    seller=seller,
                    amount=1000000  # 1 million Rials each
                )
                request.approve(processed_by='test_system')
        
        # Create phone numbers
        for i in range(200):
            PhoneNumber.objects.create(
                number=f"0912{str(i).zfill(7)}"
            )
        
        print(f"✓ Created {Seller.objects.count()} sellers")
        print(f"✓ Created {CreditRequest.objects.count()} credit requests (all approved)")
        print(f"✓ Created {PhoneNumber.objects.count()} phone numbers")
        
        for seller in Seller.objects.all():
            print(f"  - {seller.name}: {seller.credit_balance:,.0f} Rials")
        
        return sellers
    
    def charge_sale_task(self, task_id):
        """
        Single charge sale task.
        
        This simulates a concurrent API call to sell a charge.
        Each task randomly selects a seller and phone number.
        """
        try:
            # Close old connection (important for multiprocessing)
            connection.close()
            
            # Randomly select seller and phone
            sellers = list(Seller.objects.filter(is_active=True))
            phones = list(PhoneNumber.objects.all())
            
            if not sellers or not phones:
                return {'success': False, 'error': 'No data available'}
            
            seller = random.choice(sellers)
            phone = random.choice(phones)
            sale_amount = Decimal('5000')  # 5,000 Rials
            
            # Perform charge sale with transaction
            with transaction.atomic():
                # Lock seller row
                locked_seller = Seller.objects.select_for_update().get(pk=seller.pk)
                
                if locked_seller.credit_balance < sale_amount:
                    return {
                        'success': False,
                        'task_id': task_id,
                        'error': 'Insufficient balance'
                    }
                
                # Deduct credit
                new_balance, txn = locked_seller.deduct_credit(sale_amount, phone)
                
                # Update phone
                phone.add_charge(sale_amount)
            
            return {
                'success': True,
                'task_id': task_id,
                'seller_id': seller.id,
                'new_balance': float(new_balance)
            }
            
        except Exception as e:
            return {
                'success': False,
                'task_id': task_id,
                'error': str(e)
            }
    
    def credit_approval_task(self, task_id):
        """
        Single credit approval task.
        
        Tests concurrent credit approvals with idempotency.
        """
        try:
            connection.close()
            
            # Create a new credit request
            sellers = list(Seller.objects.all())
            if not sellers:
                return {'success': False, 'error': 'No sellers available'}
            
            seller = random.choice(sellers)
            amount = random.choice([100000, 200000, 300000])
            
            # Create and approve
            request = CreditRequest.objects.create(
                seller=seller,
                amount=amount
            )
            
            with transaction.atomic():
                request.approve(processed_by=f'concurrent_task_{task_id}')
            
            return {
                'success': True,
                'task_id': task_id,
                'request_id': request.id,
                'seller_id': seller.id,
                'amount': float(amount)
            }
            
        except Exception as e:
            return {
                'success': False,
                'task_id': task_id,
                'error': str(e)
            }
    
    def run_threading_test(self, num_workers=10, num_tasks=100):
        """
        Run test using multithreading.
        
        In Python, threads share the same memory space but are limited by the GIL
        (Global Interpreter Lock), which allows only one thread to execute Python
        bytecode at a time. This is suitable for I/O-bound operations like database
        queries, but not for CPU-bound operations.
        """
        print("\n" + "="*70)
        print(f"MULTITHREADING TEST: {num_workers} threads, {num_tasks} tasks")
        print("="*70)
        print("Note: Threads share memory but GIL limits parallel execution")
        print("      Good for I/O-bound operations (like database queries)")
        
        start_time = time.time()
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(self.charge_sale_task, i)
                for i in range(num_tasks)
            ]
            
            for future in as_completed(futures):
                result = future.result()
                if result['success']:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    if 'error' in result and result['error'] != 'Insufficient balance':
                        results['errors'].append(result['error'])
        
        elapsed = time.time() - start_time
        
        print(f"\n✓ Completed in {elapsed:.3f}s")
        print(f"  - Successful: {results['success']}")
        print(f"  - Failed: {results['failed']}")
        print(f"  - Throughput: {num_tasks/elapsed:.1f} tasks/sec")
        
        if results['errors']:
            print(f"  - Errors: {len(results['errors'])}")
            for error in results['errors'][:5]:
                print(f"    • {error}")
        
        self.results['threading'] = {
            'elapsed': elapsed,
            'success': results['success'],
            'failed': results['failed'],
            'throughput': num_tasks/elapsed
        }
        
        return results
    
    def run_multiprocessing_test(self, num_workers=4, num_tasks=100):
        """
        Run test using multiprocessing.
        
        Multiprocessing creates separate Python processes, each with its own
        memory space and Python interpreter. This bypasses the GIL and allows
        true parallel execution. Each process has its own database connection.
        
        This is suitable for CPU-bound operations and when true parallelism
        is needed.
        """
        print("\n" + "="*70)
        print(f"MULTIPROCESSING TEST: {num_workers} processes, {num_tasks} tasks")
        print("="*70)
        print("Note: Each process has separate memory and Python interpreter")
        print("      Bypasses GIL, true parallel execution")
        print(f"      CPU cores available: {cpu_count()}")
        
        start_time = time.time()
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        # Important: Close connection before forking
        connection.close()
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(self.charge_sale_task, i)
                for i in range(num_tasks)
            ]
            
            for future in as_completed(futures):
                result = future.result()
                if result['success']:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    if 'error' in result and result['error'] != 'Insufficient balance':
                        results['errors'].append(result['error'])
        
        elapsed = time.time() - start_time
        
        print(f"\n✓ Completed in {elapsed:.3f}s")
        print(f"  - Successful: {results['success']}")
        print(f"  - Failed: {results['failed']}")
        print(f"  - Throughput: {num_tasks/elapsed:.1f} tasks/sec")
        
        if results['errors']:
            print(f"  - Errors: {len(results['errors'])}")
            for error in results['errors'][:5]:
                print(f"    • {error}")
        
        self.results['multiprocessing'] = {
            'elapsed': elapsed,
            'success': results['success'],
            'failed': results['failed'],
            'throughput': num_tasks/elapsed
        }
        
        return results
    
    def verify_accounting_integrity(self):
        """
        Verify that accounting is still correct after concurrent operations.
        
        This is the critical test: despite heavy concurrent load, the
        accounting must still be 100% accurate.
        """
        print("\n" + "="*70)
        print("VERIFYING ACCOUNTING INTEGRITY")
        print("="*70)
        
        all_reconciled = True
        
        for seller in Seller.objects.all():
            transactions = Transaction.objects.filter(seller=seller)
            calculated_balance = sum(t.amount for t in transactions)
            
            is_reconciled = seller.credit_balance == calculated_balance
            all_reconciled = all_reconciled and is_reconciled
            
            status = "✓" if is_reconciled else "✗"
            print(f"\n{status} {seller.name}:")
            print(f"  Current balance: {seller.credit_balance:,.0f} Rials")
            print(f"  Calculated: {calculated_balance:,.0f} Rials")
            print(f"  Transactions: {transactions.count()}")
            
            if not is_reconciled:
                diff = seller.credit_balance - calculated_balance
                print(f"  ⚠ MISMATCH: {diff:,.0f} Rials")
        
        print("\n" + "="*70)
        if all_reconciled:
            print("✓ ALL SELLERS RECONCILED - ACCOUNTING IS CORRECT!")
        else:
            print("✗ ACCOUNTING MISMATCH DETECTED!")
        print("="*70)
        
        return all_reconciled
    
    def run_stress_test(self):
        """
        Run comprehensive stress test combining both threading and multiprocessing.
        """
        print("\n" + "="*70)
        print("COMPREHENSIVE CONCURRENT STRESS TEST")
        print("="*70)
        print("This test verifies system behavior under heavy concurrent load")
        print("using both multithreading and multiprocessing.")
        
        # Setup
        self.setup_test_data()
        
        # Record initial state
        initial_total_balance = sum(
            seller.credit_balance for seller in Seller.objects.all()
        )
        initial_transactions = Transaction.objects.count()
        
        print(f"\nInitial state:")
        print(f"  Total balance: {initial_total_balance:,.0f} Rials")
        print(f"  Total transactions: {initial_transactions}")
        
        # Run threading test
        self.run_threading_test(num_workers=20, num_tasks=500)
        
        # Verify accounting after threading
        threading_ok = self.verify_accounting_integrity()
        
        # Run multiprocessing test
        self.run_multiprocessing_test(
            num_workers=min(cpu_count(), 8),
            num_tasks=500
        )
        
        # Verify accounting after multiprocessing
        multiprocessing_ok = self.verify_accounting_integrity()
        
        # Final statistics
        final_total_balance = sum(
            seller.credit_balance for seller in Seller.objects.all()
        )
        final_transactions = Transaction.objects.count()
        
        print("\n" + "="*70)
        print("FINAL STATISTICS")
        print("="*70)
        print(f"Initial balance: {initial_total_balance:,.0f} Rials")
        print(f"Final balance: {final_total_balance:,.0f} Rials")
        print(f"Total spent: {initial_total_balance - final_total_balance:,.0f} Rials")
        print(f"Transactions: {initial_transactions} → {final_transactions} "
              f"(+{final_transactions - initial_transactions})")
        
        print("\n" + "="*70)
        print("THREADING vs MULTIPROCESSING COMPARISON")
        print("="*70)
        
        if 'threading' in self.results and 'multiprocessing' in self.results:
            t = self.results['threading']
            m = self.results['multiprocessing']
            
            print(f"\nThreading:")
            print(f"  Time: {t['elapsed']:.3f}s")
            print(f"  Throughput: {t['throughput']:.1f} tasks/sec")
            print(f"  Success rate: {t['success']/(t['success']+t['failed'])*100:.1f}%")
            
            print(f"\nMultiprocessing:")
            print(f"  Time: {m['elapsed']:.3f}s")
            print(f"  Throughput: {m['throughput']:.1f} tasks/sec")
            print(f"  Success rate: {m['success']/(m['success']+m['failed'])*100:.1f}%")
            
            speedup = t['elapsed'] / m['elapsed'] if m['elapsed'] > 0 else 1
            print(f"\nSpeedup: {speedup:.2f}x")
        
        print("\n" + "="*70)
        if threading_ok and multiprocessing_ok:
            print("✓ ALL TESTS PASSED - SYSTEM IS CONCURRENT-SAFE!")
        else:
            print("✗ ACCOUNTING ERRORS DETECTED!")
        print("="*70 + "\n")
        
        return threading_ok and multiprocessing_ok


def main():
    """Main entry point for concurrent tests."""
    runner = ConcurrentTestRunner()
    
    try:
        success = runner.run_stress_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
