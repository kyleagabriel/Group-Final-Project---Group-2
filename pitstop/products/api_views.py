from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User

from .models import Product, Order, Booking, Profile
from .serializers import (
    ProductSerializer,
    OrderSerializer,
    BookingSerializer,
    ProfileSerializer,
)


class ProductListAPIView(generics.ListAPIView):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        brand = self.request.query_params.get("brand")
        model = self.request.query_params.get("model")
        year = self.request.query_params.get("year")

        if brand:
            qs = qs.filter(brand__iexact=brand)
        if model:
            qs = qs.filter(model__iexact=model)
        if year:
            qs = qs.filter(compatible_years__icontains=year)

        return qs


class ProfileAPIView(generics.RetrieveAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return Profile.objects.get(user=self.request.user)


class OrderListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BookingListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, "profile") and user.profile.account_type == "installer":
            return Booking.objects.filter(installer=user)

        return Booking.objects.filter(customer=user)

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)


class AdminSummaryAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        total_sales = Order.objects.count()
        total_bookings = Booking.objects.count()
        total_products = Product.objects.count()
        total_users = User.objects.count()

        return Response({
            "total_sales": total_sales,
            "total_bookings": total_bookings,
            "total_products": total_products,
            "total_users": total_users,
        })
