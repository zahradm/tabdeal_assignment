"""
Serializers for the B2B charge sales API.
"""

from rest_framework import serializers
from .models import Seller, CreditRequest, PhoneNumber, Transaction


class SellerSerializer(serializers.ModelSerializer):
    """Serializer for Seller model."""
    
    class Meta:
        model = Seller
        fields = ['id', 'name', 'email', 'phone', 'credit_balance', 'is_active', 'created_at']
        read_only_fields = ['id', 'credit_balance', 'created_at']


class CreditRequestSerializer(serializers.ModelSerializer):
    """Serializer for CreditRequest model."""
    
    seller_name = serializers.CharField(source='seller.name', read_only=True)
    
    class Meta:
        model = CreditRequest
        fields = [
            'id', 'seller', 'seller_name', 'amount', 'status',
            'requested_at', 'processed_at', 'processed_by', 'notes'
        ]
        read_only_fields = ['id', 'status', 'requested_at', 'processed_at', 'processed_by']


class CreditRequestApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting credit requests."""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True)
    processed_by = serializers.CharField(default='admin')


class ChargeSaleSerializer(serializers.Serializer):
    """Serializer for charge sale operations."""
    
    seller_id = serializers.IntegerField()
    phone_number = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01)
    
    def validate_seller_id(self, value):
        """Validate that seller exists and is active."""
        try:
            seller = Seller.objects.get(pk=value)
            if not seller.is_active:
                raise serializers.ValidationError("Seller is not active")
        except Seller.DoesNotExist:
            raise serializers.ValidationError("Seller not found")
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number format."""
        # Remove any non-digit characters
        cleaned = ''.join(filter(str.isdigit, value))
        if len(cleaned) < 10:
            raise serializers.ValidationError("Invalid phone number format")
        return cleaned


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model."""
    
    seller_name = serializers.CharField(source='seller.name', read_only=True)
    phone_number_value = serializers.CharField(source='phone_number.number', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'seller', 'seller_name', 'transaction_type', 'amount',
            'balance_after', 'credit_request', 'phone_number', 'phone_number_value',
            'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PhoneNumberSerializer(serializers.ModelSerializer):
    """Serializer for PhoneNumber model."""
    
    class Meta:
        model = PhoneNumber
        fields = ['id', 'number', 'total_charged', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_charged', 'created_at', 'updated_at']
