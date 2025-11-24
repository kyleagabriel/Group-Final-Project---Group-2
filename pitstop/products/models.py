from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

class Product(models.Model):
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="products",
    )
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)

    # 🔹 NEW: years the part is compatible with
    compatible_years = models.CharField(max_length=200, blank=True)

    def year_range(self):
        if not self.compatible_years:
            return None
        
        years = sorted({int(y.strip()) for y in self.compatible_years.split(",") if y.strip().isdigit()})

        if not years:
            return None

        # If only 1 year exists
        if len(years) == 1:
            return str(years[0])

        return f"{years[0]}–{years[-1]}"

    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)

    # 🔹 NEW: product image
    image = models.ImageField(
        upload_to="product_images/",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_type = models.CharField(max_length=20, default="customer")

    # 🧮 OLD (from quantity-based vouchers) – you can keep these, even if unused now
    total_products_purchased = models.PositiveIntegerField(default=0)
    five_percent_voucher_used = models.BooleanField(default=False)
    ten_percent_voucher_used = models.BooleanField(default=False)
    twenty_percent_voucher_used = models.BooleanField(default=False)

    # 🆕 NEW – peso-based voucher logic
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # one-time vouchers by spend
    voucher_5_used = models.BooleanField(default=False)   # 5% after ₱5k spent
    voucher_10_used = models.BooleanField(default=False)  # 10% after ₱10k spent
    voucher_20_used = models.BooleanField(default=False)  # 20% after ₱20k spent

    # repeatable ₱250 vouchers (every ₱5k after ₱20k)
    extra_voucher_balance = models.PositiveIntegerField(default=0)
    extra_vouchers_earned = models.PositiveIntegerField(default=0)

    # saved car for filter shortcut
    saved_car_brand = models.CharField(max_length=100, blank=True)
    saved_car_model = models.CharField(max_length=100, blank=True)
    saved_car_year = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"




class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    total = models.DecimalField(max_digits=10, decimal_places=2)
    applied_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_total = models.DecimalField(max_digits=10, decimal_places=2)
    voucher_code = models.CharField(max_length=20, blank=True)
    payment_method = models.CharField(max_length=20, blank=True)

    convenience_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # 🆕 delivery tracking
    delivery_days = models.PositiveIntegerField(default=0)          # randomized 1–5
    delivery_eta = models.DateField(null=True, blank=True)          # estimated delivery date

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    # 🆕 helper: current delivery stage text
    def delivery_stage(self):
        from django.utils import timezone

        if not self.delivery_days or not self.delivery_eta:
            return "Awaiting dispatch"

        today = timezone.now().date()
        days_since = (today - self.created_at.date()).days

        if days_since <= 0:
            return "Seller is packing"
        elif days_since < self.delivery_days - 1:
            return "Sent to courier"
        elif days_since < self.delivery_days:
            return "Delivering to your address"
        else:
            return "Delivered"

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )

    product_name = models.CharField(max_length=255)
    brand = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.product_name} x{self.quantity} (Order #{self.order_id})"
    
class Booking(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="customer_bookings",
    )
    installer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="installer_bookings",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )

    # Car details
    car_brand = models.CharField(max_length=120, blank=True)
    car_model = models.CharField(max_length=120, blank=True)
    car_year = models.CharField(max_length=10, blank=True)

    # Schedule
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()

    # Booking status + platform fee
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    finders_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking #{self.id} for {self.product.name if self.product else 'Unknown part'}"
