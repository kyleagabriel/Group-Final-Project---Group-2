from django.urls import path
from .api_views import (
    ProductListAPIView,
    OrderListCreateAPIView,
    BookingListCreateAPIView,
    ProfileAPIView,
    AdminSummaryAPIView,
)

urlpatterns = [
    path("products/", ProductListAPIView.as_view(), name="api-products"),
    path("orders/", OrderListCreateAPIView.as_view(), name="api-orders"),
    path("bookings/", BookingListCreateAPIView.as_view(), name="api-bookings"),
    path("profile/", ProfileAPIView.as_view(), name="api-profile"),
    path("admin/summary/", AdminSummaryAPIView.as_view(), name="api-admin-summary"),
]
