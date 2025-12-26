"""
Simple script to create sample data for testing and demonstration.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from sales.models import Seller, CreditRequest, PhoneNumber


def create_sample_data():
    """Create sample sellers, credit requests, and phone numbers."""
    
    print("Creating sample data...")
    print("-" * 50)
    
    # Create sellers
    sellers = []
    seller_data = [
        {"name": "فروشگاه الف", "email": "shop.a@example.com", "phone": "09121111111"},
        {"name": "فروشگاه ب", "email": "shop.b@example.com", "phone": "09122222222"},
        {"name": "فروشگاه ج", "email": "shop.c@example.com", "phone": "09123333333"},
    ]
    
    for data in seller_data:
        seller, created = Seller.objects.get_or_create(
            email=data['email'],
            defaults=data
        )
        if created:
            print(f"✓ Created seller: {seller.name}")
        else:
            print(f"• Seller already exists: {seller.name}")
        sellers.append(seller)
    
    print()
    
    # Create credit requests
    print("Creating credit requests...")
    credit_amounts = [500000, 750000, 1000000]
    
    for seller in sellers:
        for i, amount in enumerate(credit_amounts):
            request, created = CreditRequest.objects.get_or_create(
                seller=seller,
                amount=amount,
                status=CreditRequest.PENDING
            )
            if created:
                print(f"✓ Created credit request: {seller.name} - {amount:,} Rials")
    
    print()
    
    # Create phone numbers
    print("Creating phone numbers...")
    for i in range(20):
        phone, created = PhoneNumber.objects.get_or_create(
            number=f"0912{str(i).zfill(7)}"
        )
        if created and i < 3:
            print(f"✓ Created phone: {phone.number}")
    
    if PhoneNumber.objects.count() > 3:
        print(f"... and {PhoneNumber.objects.count() - 3} more")
    
    print()
    print("-" * 50)
    print("Sample data creation completed!")
    print()
    print("Summary:")
    print(f"  Sellers: {Seller.objects.count()}")
    print(f"  Pending credit requests: {CreditRequest.objects.filter(status='pending').count()}")
    print(f"  Phone numbers: {PhoneNumber.objects.count()}")
    print()
    print("Next steps:")
    print("1. Go to admin panel: http://localhost:8000/admin/")
    print("2. Approve some credit requests")
    print("3. Try the charge sale API")
    print()


if __name__ == '__main__':
    create_sample_data()
