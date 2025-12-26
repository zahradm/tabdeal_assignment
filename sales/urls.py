"""
URL configuration for sales app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SellerViewSet,
    CreditRequestViewSet,
    ChargeSaleViewSet,
    TransactionViewSet,
    PhoneNumberViewSet
)

router = DefaultRouter()
router.register(r'sellers', SellerViewSet, basename='seller')
router.register(r'credit-requests', CreditRequestViewSet, basename='credit-request')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'phone-numbers', PhoneNumberViewSet, basename='phone-number')

urlpatterns = [
    path('', include(router.urls)),
    path('charge-sales/', ChargeSaleViewSet.as_view({'post': 'create'}), name='charge-sale'),
]
