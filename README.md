# B2B Charge Sales System (Tabdeal Assignment)

A robust, production-ready B2B charge sales system built with Django and Django REST Framework. This system handles credit management and charge sales with full protection against race conditions, double-spending, and accounting inconsistencies.

## 🎯 Project Overview

This system enables sellers to:
- Request credit increases (requires admin approval)
- Sell phone charges to customers
- Track all financial transactions with full audit trail
- Maintain accounting integrity under heavy concurrent load

## ✨ Key Features

### 🔒 Concurrency Safety
- **Atomic Transactions**: All financial operations use database-level atomicity
- **Row-Level Locking**: `select_for_update()` prevents race conditions
- **Idempotent Operations**: Credit requests can only be approved once
- **Database Constraints**: Prevents negative balances at the database level

### 📊 Accounting Integrity
- **Immutable Transaction Log**: Complete audit trail of all operations
- **Reconciliation Support**: Balance verification against transaction history
- **Double-Spend Prevention**: Database constraints ensure financial consistency

### 🚀 Performance
- **Concurrent Request Handling**: Tested with 1000+ concurrent operations
- **Process-Safe**: Works correctly with multiprocessing (Gunicorn/uWSGI)
- **Thread-Safe**: Handles multithreaded scenarios correctly

## 🏗️ Architecture

### Database Models

```
┌─────────────┐
│   Seller    │
├─────────────┤
│ id          │
│ name        │
│ email       │
│ phone       │
│ credit_     │
│  balance    │◄─────┐
│ is_active   │      │
│ created_at  │      │
└─────────────┘      │
       │             │
       │             │
       ▼             │
┌─────────────┐      │
│CreditRequest│      │
├─────────────┤      │
│ id          │      │
│ seller_id   │      │
│ amount      │      │
│ status      │      │
│ requested_at│      │
│ processed_at│      │
└─────────────┘      │
       │             │
       │             │
       ▼             │
┌─────────────┐      │
│ Transaction │      │
├─────────────┤      │
│ id          │──────┘
│ seller_id   │
│ type        │
│ amount      │
│ balance_    │
│  after      │
│ credit_req  │
│ phone_num   │
│ description │
│ created_at  │
└─────────────┘
       │
       │
       ▼
┌─────────────┐
│PhoneNumber  │
├─────────────┤
│ id          │
│ number      │
│ total_      │
│  charged    │
│ created_at  │
└─────────────┘
```

### Key Design Decisions

1. **Transaction Immutability**: Once created, transactions cannot be modified or deleted
2. **Status-Based Processing**: Credit requests use state machine pattern (pending → approved/rejected)
3. **Balance Constraints**: Database-level CHECK constraints prevent negative balances
4. **Proper Indexing**: Strategic indexes on foreign keys and frequently queried fields

## 📋 Requirements

- Python 3.8+
- PostgreSQL 12+
- Django 4.2+
- Django REST Framework 3.14+

## 🚀 Installation & Setup

### 1. Clone and Setup Environment

```bash
cd /home/zahra/projects/tabdeal_assignment

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Database

Create PostgreSQL database:

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE tabdeal_db;
CREATE USER tabdeal_user WITH PASSWORD 'your_password';
ALTER ROLE tabdeal_user SET client_encoding TO 'utf8';
ALTER ROLE tabdeal_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE tabdeal_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE tabdeal_db TO tabdeal_user;
\q
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
SECRET_KEY=your-secret-key-here-generate-a-strong-one
DEBUG=True
DATABASE_NAME=tabdeal_db
DATABASE_USER=tabdeal_user
DATABASE_PASSWORD=your_password
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

### 4. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create Superuser

```bash
python manage.py createsuperuser
```

### 6. Run Development Server

```bash
python manage.py runserver
```

Access the application at: http://localhost:8000

## 🔌 API Endpoints

### Sellers

```bash
# List all sellers
GET /api/sellers/

# Create seller
POST /api/sellers/
{
  "name": "Seller Name",
  "email": "seller@example.com",
  "phone": "09121234567"
}

# Get seller balance
GET /api/sellers/{id}/balance/

# Get seller transactions
GET /api/sellers/{id}/transactions/

# Reconcile seller balance
GET /api/sellers/{id}/reconcile/
```

### Credit Requests

```bash
# List credit requests
GET /api/credit-requests/
GET /api/credit-requests/?status=pending

# Create credit request
POST /api/credit-requests/
{
  "seller": 1,
  "amount": 1000000
}

# Approve/Reject credit request
POST /api/credit-requests/{id}/process/
{
  "action": "approve",  # or "reject"
  "processed_by": "admin_username"
}
```

### Charge Sales (Main Operation)

```bash
# Sell a charge
POST /api/charge-sales/
{
  "seller_id": 1,
  "phone_number": "09123456789",
  "amount": 50000
}

# Response (success)
{
  "status": "success",
  "message": "Charge sale completed",
  "transaction_id": 123,
  "seller_id": 1,
  "phone_number": "09123456789",
  "amount": "50000.00",
  "new_balance": "450000.00"
}

# Response (insufficient balance)
{
  "error": "Insufficient balance",
  "available_balance": "30000.00",
  "required_amount": "50000.00",
  "shortage": "20000.00"
}
```

### Transactions

```bash
# List all transactions
GET /api/transactions/

# Filter by seller
GET /api/transactions/?seller_id=1

# Filter by type
GET /api/transactions/?type=charge_sale
GET /api/transactions/?type=credit_increase
```

## 🧪 Testing

### Run Basic Tests

```bash
# Run all Django tests
python manage.py test sales

# Run with verbose output
python manage.py test sales -v 2

# Run specific test
python manage.py test sales.tests.RequiredScenarioTestCase.test_required_scenario
```

Expected output for the required scenario test:
```
======================================================================
REQUIRED SCENARIO TEST: 2 Sellers, 10 Credit Increases, 1000 Sales
======================================================================

[1] Creating 10 credit increase requests...
   ✓ Created 10 credit requests

[2] Approving all credit requests...
   ✓ Approved 10 requests in 0.XXXs
   ✓ Seller 1 balance: 5,000,000 Rials
   ✓ Seller 2 balance: 5,000,000 Rials

[3] Performing 1000 charge sales...
   ✓ Completed 1000 sales in X.XXXs
   ✓ Average: XX.XXms per sale

[4] Verifying final balances...
   ✓ Seller 1 final balance: 2,500,000 Rials
   ✓ Seller 2 final balance: 2,500,000 Rials
   ✓ Expected balance: 2,500,000 Rials

[5] Reconciling accounting...
   ✓ Accounting is reconciled!

ALL TESTS PASSED ✓
```

### Run Concurrent Load Tests

```bash
# Run concurrent stress tests (multiprocessing + multithreading)
python test_concurrent.py
```

This test:
- Creates 5 sellers with initial credit
- Runs 500 concurrent charge sales using multithreading
- Runs 500 concurrent charge sales using multiprocessing
- Verifies accounting integrity after each test
- Demonstrates understanding of Python GIL and concurrency models

Expected output:
```
======================================================================
COMPREHENSIVE CONCURRENT STRESS TEST
======================================================================

MULTITHREADING TEST: 20 threads, 500 tasks
Note: Threads share memory but GIL limits parallel execution
✓ Completed in X.XXXs
  - Successful: XXX
  - Throughput: XXX tasks/sec

MULTIPROCESSING TEST: 8 processes, 500 tasks
Note: Each process has separate memory and Python interpreter
✓ Completed in X.XXXs
  - Successful: XXX
  - Throughput: XXX tasks/sec

VERIFYING ACCOUNTING INTEGRITY
✓ ALL SELLERS RECONCILED - ACCOUNTING IS CORRECT!

✓ ALL TESTS PASSED - SYSTEM IS CONCURRENT-SAFE!
```

## 🔐 Concurrency Protection Mechanisms

### 1. Database Row Locking

```python
# In models.py - deduct_credit method
seller = Seller.objects.select_for_update().get(pk=self.pk)
```

This acquires an exclusive lock on the seller row, forcing concurrent transactions to wait.

### 2. Atomic Transactions

```python
@transaction.atomic
def deduct_credit(self, amount, phone_number):
    # All operations succeed or fail together
    # Database rollback on any error
```

### 3. Database Constraints

```python
class Meta:
    constraints = [
        models.CheckConstraint(
            check=models.Q(credit_balance__gte=0),
            name='seller_credit_balance_non_negative'
        )
    ]
```

### 4. Status-Based Idempotency

```python
if credit_request.status != self.PENDING:
    raise ValueError("Only pending requests can be approved")
```

## 🎓 Understanding Multi-threading vs Multi-processing in Python

### Multi-threading
- **What**: Multiple threads in a single process
- **Memory**: Shared memory space
- **GIL Impact**: Only one thread executes Python bytecode at a time
- **Best For**: I/O-bound operations (database queries, API calls)
- **In This Project**: Good for handling concurrent API requests

```python
# Example from test_concurrent.py
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(charge_sale_task, i) for i in range(500)]
```

### Multi-processing
- **What**: Multiple separate Python processes
- **Memory**: Each process has its own memory space
- **GIL Impact**: No GIL limitation - true parallelism
- **Best For**: CPU-bound operations
- **In This Project**: Better throughput for parallel operations

```python
# Example from test_concurrent.py
with ProcessPoolExecutor(max_workers=cpu_count()) as executor:
    futures = [executor.submit(charge_sale_task, i) for i in range(500)]
```

### Key Differences Demonstrated

1. **Connection Handling**: Each process needs `connection.close()` before forking
2. **Performance**: Multiprocessing often faster due to true parallelism
3. **Resource Usage**: Multiprocessing uses more memory
4. **Database Safety**: Both work correctly due to database-level locking

## 📊 Admin Interface

Access Django admin at: http://localhost:8000/admin/

### Features:
- **Sellers**: View and manage sellers
- **Credit Requests**: Approve/reject with bulk actions
- **Transactions**: Read-only view of all transactions
- **Phone Numbers**: View charged phone numbers

## 🔍 Accounting Reconciliation

The system provides a reconciliation endpoint to verify accounting integrity:

```bash
curl http://localhost:8000/api/sellers/1/reconcile/
```

Response:
```json
{
  "seller_id": 1,
  "name": "Seller Name",
  "current_balance": "1500000.00",
  "calculated_from_transactions": "1500000.00",
  "is_reconciled": true,
  "difference": "0.00",
  "total_transactions": 25
}
```

## 🛡️ Security Considerations

1. **SQL Injection**: Protected by Django ORM parameterized queries
2. **Race Conditions**: Protected by `select_for_update()` and atomic transactions
3. **Double Spending**: Protected by database constraints and status checks
4. **Negative Balances**: Prevented by database CHECK constraints
5. **Transaction Tampering**: Transactions are immutable

## 📈 Production Deployment Considerations

### 1. Database Configuration
- Use PostgreSQL with proper connection pooling
- Set appropriate `max_connections` and `shared_buffers`
- Enable query logging for audit

### 2. Application Server
- Use Gunicorn or uWSGI with multiple workers
- Configure worker count based on CPU cores: `workers = (2 * cpu_count) + 1`
- Enable worker timeout for long-running requests

### 3. Caching
- Use Redis for session storage
- Cache frequently accessed data (seller balances, etc.)
- Implement cache invalidation strategy

### 4. Monitoring
- Track transaction throughput
- Monitor database lock waits
- Alert on reconciliation failures

## 📝 Project Deliverables Checklist

✅ **Architecture and Model Definition**
- Well-designed models with proper relationships
- Database constraints for data integrity
- Strategic indexing for performance

✅ **Idempotent Credit Increase**
- Credit requests can only be approved once
- Protected by status checks and database constraints
- Cannot be re-saved to increase credit multiple times

✅ **Proper Transaction Logging**
- Every credit increase logged
- Every charge sale logged
- Immutable transaction records

✅ **Negative Balance Prevention (Sales)**
- Balance check before deduction
- Database constraint as fallback
- Atomic transaction ensures consistency

✅ **Negative Balance Prevention (Credit Operations)**
- Database CHECK constraint
- Application-level validation

✅ **Race Condition & Double-Spend Protection**
- `select_for_update()` for row locking
- Atomic transactions
- Database-level constraints

✅ **Basic Test Case**
- 2 sellers ✓
- 10 credit increases ✓
- 1000 charge sales ✓
- Balance verification ✓

✅ **Concurrent Load Testing**
- Multi-threading test ✓
- Multi-processing test ✓
- Accounting verification under load ✓

✅ **Multi-threading vs Multi-processing Understanding**
- GIL explanation ✓
- Practical demonstration ✓
- Performance comparison ✓

## 👨‍💻 Author

Zahra - Tabdeal Assignment

## 📄 License

This project is created as part of a technical assessment.
