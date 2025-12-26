"""
Django admin configuration for sales app.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Seller, CreditRequest, PhoneNumber, Transaction


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    """Admin interface for Seller model."""
    
    list_display = ['id', 'name', 'email', 'phone', 'credit_balance', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'email', 'phone']
    readonly_fields = ['credit_balance', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'email', 'phone', 'is_active')
        }),
        ('Financial Information', {
            'fields': ('credit_balance',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CreditRequest)
class CreditRequestAdmin(admin.ModelAdmin):
    """Admin interface for CreditRequest model with approval/rejection actions."""
    
    list_display = [
        'id', 'seller', 'amount', 'status_badge', 'requested_at', 
        'processed_at', 'processed_by'
    ]
    list_filter = ['status', 'requested_at', 'processed_at']
    search_fields = ['seller__name', 'seller__email']
    readonly_fields = ['requested_at', 'processed_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('seller', 'amount', 'status')
        }),
        ('Processing Information', {
            'fields': ('processed_at', 'processed_by', 'notes')
        }),
        ('Timestamps', {
            'fields': ('requested_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_requests', 'reject_requests']
    
    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def approve_requests(self, request, queryset):
        """Bulk approve pending credit requests."""
        approved = 0
        errors = []
        
        for credit_request in queryset:
            try:
                if credit_request.status == CreditRequest.PENDING:
                    credit_request.approve(processed_by=request.user.username)
                    approved += 1
            except ValueError as e:
                errors.append(f"Request #{credit_request.id}: {str(e)}")
        
        if approved:
            self.message_user(request, f"Successfully approved {approved} credit request(s).")
        if errors:
            self.message_user(request, f"Errors: {'; '.join(errors)}", level='warning')
    
    approve_requests.short_description = "Approve selected credit requests"
    
    def reject_requests(self, request, queryset):
        """Bulk reject pending credit requests."""
        rejected = 0
        errors = []
        
        for credit_request in queryset:
            try:
                if credit_request.status == CreditRequest.PENDING:
                    credit_request.reject(
                        processed_by=request.user.username,
                        reason="Rejected via admin bulk action"
                    )
                    rejected += 1
            except ValueError as e:
                errors.append(f"Request #{credit_request.id}: {str(e)}")
        
        if rejected:
            self.message_user(request, f"Successfully rejected {rejected} credit request(s).")
        if errors:
            self.message_user(request, f"Errors: {'; '.join(errors)}", level='warning')
    
    reject_requests.short_description = "Reject selected credit requests"


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    """Admin interface for PhoneNumber model."""
    
    list_display = ['id', 'number', 'total_charged', 'created_at', 'updated_at']
    search_fields = ['number']
    readonly_fields = ['total_charged', 'created_at', 'updated_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin interface for Transaction model (read-only)."""
    
    list_display = [
        'id', 'seller', 'transaction_type', 'amount_display', 
        'balance_after', 'created_at'
    ]
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['seller__name', 'description']
    readonly_fields = [
        'seller', 'transaction_type', 'amount', 'balance_after',
        'credit_request', 'phone_number', 'description', 'created_at'
    ]
    
    def amount_display(self, obj):
        """Display amount with color coding."""
        color = 'green' if obj.amount > 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:,.2f}</span>',
            color,
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def has_add_permission(self, request):
        """Transactions cannot be created manually."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Transactions cannot be deleted."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Transactions cannot be modified."""
        return False
