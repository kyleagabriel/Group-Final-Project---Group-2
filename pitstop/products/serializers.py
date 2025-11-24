from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Product, Order, OrderItem, Booking, Profile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    seller = UserSerializer(read_only=True)

    class Meta:
        model = Product
        fields = "__all__"


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "product",
            "product_name",
            "brand",
            "model",
            "unit_price",
            "quantity",
        ]


class OrderSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "created_at",
            "total",
            "applied_discount",
            "final_total",
            "voucher_code",
            "payment_method",
            "convenience_fee",
            "delivery_days",
            "delivery_eta",
            "items",
        ]


class BookingSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    installer = UserSerializer(read_only=True)
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = "__all__"
