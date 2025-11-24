from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from urllib.parse import urlencode
from .models import Product, Profile, Order, OrderItem, Booking
from .forms import SignUpForm, SellerProductForm, BookingForm
from decimal import Decimal
from io import BytesIO
import base64
import qrcode
import random
from datetime import timedelta
from django.utils import timezone
from collections import defaultdict

def product_list(request):
    # 🔒 redirect sellers to their area
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile:
            if profile.account_type == "seller":
                return redirect("seller_dashboard")
            if profile.account_type == "installer":
                return redirect("installer_dashboard")

    products_qs = Product.objects.all()

    # 🧷 1) Handle "Save this car" (POST) – only save, don't auto-apply
    if request.method == "POST" and request.user.is_authenticated:
        brand = (request.POST.get("save_car_brand") or "").strip()
        model = (request.POST.get("save_car_model") or "").strip()
        year = (request.POST.get("save_car_year") or "").strip()

        profile = request.user.profile
        profile.saved_car_brand = brand
        profile.saved_car_model = model
        profile.saved_car_year = year
        profile.save()

        params = {}
        if brand:
            params["car_brand"] = brand
        if model:
            params["car_model"] = model
        if year:
            params["car_year"] = year

        url = reverse("product_list")
        if params:
            url = f"{url}?{urlencode(params)}"
        return redirect(url)

    # 🔍 2) Normal filters from GET
    car_brand = request.GET.get("car_brand", "").strip()
    car_model = request.GET.get("car_model", "").strip()
    car_year = request.GET.get("car_year", "").strip()

    if car_brand:
        products_qs = products_qs.filter(brand__icontains=car_brand)
    if car_model:
        products_qs = products_qs.filter(model__icontains=car_model)
    if car_year:
        products_qs = products_qs.filter(compatible_years__icontains=car_year)

    # 💾 3) Get saved car (only for display / shortcut)
    saved_car = {"brand": "", "model": "", "year": ""}

    if request.user.is_authenticated:
        profile = request.user.profile
        saved_car = {
            "brand": profile.saved_car_brand or "",
            "model": profile.saved_car_model or "",
            "year": profile.saved_car_year or "",
        }

    # 🛡️ 4) Attach badge info per seller based on lifetime revenue
    # convert queryset to list so we can attach attributes
    products = list(products_qs.select_related("seller"))

    seller_ids = {p.seller_id for p in products}
    revenue_by_seller = defaultdict(Decimal)

    if seller_ids:
        # all order items belonging to these sellers
        seller_items = (
            OrderItem.objects
            .filter(product__seller_id__in=seller_ids)
            .select_related("product")
        )
        for item in seller_items:
            revenue_by_seller[item.product.seller_id] += item.unit_price * item.quantity

    THRESH_VERIFIED = Decimal("10000")   # ₱10,000
    THRESH_TOP = Decimal("100000")       # ₱100,000

    for p in products:
        seller_rev = revenue_by_seller.get(p.seller_id, Decimal("0"))
        if seller_rev >= THRESH_TOP:
            p.badge_level = "top"
        elif seller_rev >= THRESH_VERIFIED:
            p.badge_level = "verified"
        else:
            p.badge_level = "none"

    context = {
        "products": products,
        "car_brand": car_brand,
        "car_model": car_model,
        "car_year": car_year,
        "saved_car": saved_car,
    }
    return render(request, "products/product_list.html", context)

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)

    raw_years = product.compatible_years or ""
    years_list = [y.strip() for y in raw_years.split(",") if y.strip()]

    return render(
        request,
        "products/product_detail.html",
        {
            "product": product,
            "years_list": years_list,   # 👈 pass cleaned list to template
        },
    )


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get("cart", {})

    try:
        qty = int(request.POST.get("quantity", 1))
    except ValueError:
        qty = 1

    qty = max(1, min(qty, product.stock))

    if str(product_id) in cart:
        cart[str(product_id)]["quantity"] += qty
    else:
        cart[str(product_id)] = {
            "name": product.name,
            "brand": product.brand,
            "model": product.model,
            "price": float(product.price),
            "quantity": qty,
        }

    request.session["cart"] = cart
    return redirect("view_cart")

@login_required
def view_cart(request):
    cart = request.session.get("cart", {})  # {product_id: {name, price, quantity, ...}}
    error = None

    # ---------- POST ACTIONS ----------
    if request.method == "POST":
        # Update quantity
        if "update" in request.POST:
            product_id = request.POST.get("product_id")
            try:
                new_qty = int(request.POST.get("quantity", 1))
            except ValueError:
                new_qty = 1

            if product_id in cart:
                product = get_object_or_404(Product, id=product_id)
                if new_qty < 1:
                    new_qty = 1
                if new_qty > product.stock:
                    new_qty = product.stock
                    error = f"Only {product.stock} pcs available for {product.name}."
                cart[product_id]["quantity"] = new_qty
                request.session["cart"] = cart

            if not error:
                return redirect("view_cart")

        # Remove line item
        elif "remove" in request.POST:
            product_id = request.POST.get("product_id")
            if product_id in cart:
                del cart[product_id]
                request.session["cart"] = cart
            return redirect("view_cart")

        # ✅ Checkout: send subtotal + voucher choice to mock_payment
        elif "checkout" in request.POST:
            if not cart:
                error = "Your cart is empty."
            else:
                # Recompute totals using floats (safe for session)
                total = 0.0
                for item in cart.values():
                    item["subtotal"] = item["price"] * item["quantity"]
                    total += item["subtotal"]

                selected_voucher_code = request.POST.get("voucher_code", "") or ""

                # store a snapshot in the session for the payment step
                request.session["pending_checkout"] = {
                    "cart": cart,
                    "total": float(total),          # subtotal BEFORE discount/fee
                    "voucher_code": selected_voucher_code,
                }
                request.session.modified = True

                return redirect("mock_payment")

    # ---------- GET or POST-with-error: compute totals & available vouchers ----------
    total = 0.0
    for item in cart.values():
        item["subtotal"] = item["price"] * item["quantity"]
        total += item["subtotal"]

    profile = request.user.profile
    total_spent = profile.total_spent or Decimal("0")

    available_vouchers = []

    if total_spent >= Decimal("5000") and not profile.five_percent_voucher_used:
        available_vouchers.append(
            {"code": "5PCT", "label": "5% off (one-time after ₱5,000 spent)"}
        )

    if total_spent >= Decimal("10000") and not profile.ten_percent_voucher_used:
        available_vouchers.append(
            {"code": "10PCT", "label": "10% off (one-time after ₱10,000 spent)"}
        )

    if total_spent >= Decimal("20000") and not profile.twenty_percent_voucher_used:
        available_vouchers.append(
            {"code": "20PCT", "label": "20% off (one-time after ₱20,000 spent)"}
        )

    if profile.extra_voucher_balance > 0:
        available_vouchers.append(
            {
                "code": "P250",
                "label": f"₱250 off (you have {profile.extra_voucher_balance})",
            }
        )

    return render(
        request,
        "products/cart.html",
        {
            "cart": cart,
            "total": total,
            "available_vouchers": available_vouchers,
            "error": error,
        },
    )





@login_required
def mock_payment(request):
    pending = request.session.get("pending_checkout")
    if not pending:
        # No pending checkout → go back to cart
        return redirect("view_cart")

    cart = pending.get("cart", {})
    total = Decimal(str(pending.get("total", 0)))  # subtotal BEFORE discounts/fee
    selected_voucher_code = pending.get("voucher_code", "") or ""
    profile = request.user.profile

    # ---------- helper to preview discount (no DB changes) ----------
    def compute_discount_preview(total_spent_before, code):
        discount = Decimal("0")
        if (
            code == "5PCT"
            and total_spent_before >= Decimal("5000")
            and not profile.five_percent_voucher_used
        ):
            discount = (total * Decimal("0.05")).quantize(Decimal("0.01"))
        elif (
            code == "10PCT"
            and total_spent_before >= Decimal("10000")
            and not profile.ten_percent_voucher_used
        ):
            discount = (total * Decimal("0.10")).quantize(Decimal("0.01"))
        elif (
            code == "20PCT"
            and total_spent_before >= Decimal("20000")
            and not profile.twenty_percent_voucher_used
        ):
            discount = (total * Decimal("0.20")).quantize(Decimal("0.01"))
        elif (
            code == "P250"
            and profile.extra_voucher_balance > 0
        ):
            discount = Decimal("250")
        return discount

    total_spent_before = profile.total_spent or Decimal("0")

    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "COD")

        # ----- compute discount (this time WITH DB changes) -----
        applied_discount = Decimal("0")

        if (
            selected_voucher_code == "5PCT"
            and total_spent_before >= Decimal("5000")
            and not profile.five_percent_voucher_used
        ):
            applied_discount = (total * Decimal("0.05")).quantize(Decimal("0.01"))
            profile.five_percent_voucher_used = True

        elif (
            selected_voucher_code == "10PCT"
            and total_spent_before >= Decimal("10000")
            and not profile.ten_percent_voucher_used
        ):
            applied_discount = (total * Decimal("0.10")).quantize(Decimal("0.01"))
            profile.ten_percent_voucher_used = True

        elif (
            selected_voucher_code == "20PCT"
            and total_spent_before >= Decimal("20000")
            and not profile.twenty_percent_voucher_used
        ):
            applied_discount = (total * Decimal("0.20")).quantize(Decimal("0.01"))
            profile.twenty_percent_voucher_used = True

        elif (
            selected_voucher_code == "P250"
            and profile.extra_voucher_balance > 0
        ):
            applied_discount = Decimal("250")
            profile.extra_voucher_balance -= 1

        else:
            selected_voucher_code = ""
            applied_discount = Decimal("0")

        # ✅ discounted total first
        discounted_total = max(total - applied_discount, Decimal("0"))

        # ✅ 5% convenience fee based on discounted total
        convenience_fee = (discounted_total * Decimal("0.05")).quantize(Decimal("0.01"))

        # final amount customer pays
        final_total = discounted_total + convenience_fee

        # ----- create Order with payment_method + randomized delivery window -----
        delivery_days = random.randint(1, 5)
        delivery_eta = timezone.now().date() + timedelta(days=delivery_days)

        order = Order.objects.create(
            user=request.user,
            total=total,
            applied_discount=applied_discount,
            final_total=final_total,
            voucher_code=selected_voucher_code,
            payment_method=payment_method,
            convenience_fee=convenience_fee,  # ✅ stored in DB
            delivery_days=delivery_days,
            delivery_eta=delivery_eta,
        )

        # ----- apply stock changes + create OrderItems -----
        for product_id, item in cart.items():
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                product = None

            if product is not None:
                product.stock = max(product.stock - item["quantity"], 0)
                product.save()

            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=item["name"],
                brand=item.get("brand", ""),
                model=item.get("model", ""),
                unit_price=item["price"],
                quantity=item["quantity"],
            )

        # ----- update profile spend history & extra vouchers -----
        current_spent = profile.total_spent or Decimal("0")
        profile.total_spent = current_spent + final_total  # includes fee

        threshold = Decimal("20000")
        block_size = Decimal("5000")

        if profile.total_spent > threshold:
            total_blocks = int((profile.total_spent - threshold) // block_size)
        else:
            total_blocks = 0

        new_blocks = total_blocks - profile.extra_vouchers_earned
        if new_blocks > 0:
            profile.extra_voucher_balance += new_blocks
            profile.extra_vouchers_earned = total_blocks

        profile.save()

        # ----- clear cart & pending checkout -----
        request.session["cart"] = {}
        if "pending_checkout" in request.session:
            del request.session["pending_checkout"]

        return render(
            request,
            "products/checkout_success.html",
            {
                "total": total,
                "applied_discount": applied_discount,
                "convenience_fee": convenience_fee,
                "final_total": final_total,
                "selected_voucher_code": selected_voucher_code,
                "order": order,
                "payment_method": payment_method,
            },
        )

    # ---------- GET: show preview (discount + fee estimate) ----------
    preview_discount = compute_discount_preview(total_spent_before, selected_voucher_code)
    preview_discounted_total = max(total - preview_discount, Decimal("0"))
    preview_convenience_fee = (preview_discounted_total * Decimal("0.05")).quantize(Decimal("0.01"))
    preview_final = preview_discounted_total + preview_convenience_fee

    # QR can reflect the estimated final total
    qr_payload = f"Pitstop.ph | user={request.user.id} | total={preview_final} | voucher={selected_voucher_code or 'NONE'}"

    qr_img = qrcode.make(qr_payload)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    qr_data_url = f"data:image/png;base64,{qr_base64}"

    return render(
        request,
        "products/payment.html",
        {
            "total": total,
            "discount_preview": preview_discount,
            "convenience_fee": preview_convenience_fee,
            "final_preview": preview_final,
            "voucher_code": selected_voucher_code,
            "qr_data_url": qr_data_url,
        },
    )


@login_required
def track_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "products/track_order.html", {"order": order})


@login_required
def transaction_history(request):
    profile = getattr(request.user, "profile", None)
    if profile and profile.account_type == "seller":
        return redirect("seller_product_list")

    orders = (
        Order.objects.filter(user=request.user)
        .order_by("-created_at")
        .prefetch_related("items")
    )

    # ⭐ Pre-compute subtotals so the template stays simple
    for order in orders:
        for item in order.items.all():
            item.subtotal = item.unit_price * item.quantity

    return render(
        request,
        "products/transaction_history.html",
        {"orders": orders},
    )

@login_required
def book_installation(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.account_type != "customer":
        return redirect("product_list")

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.customer = request.user
            booking.status = "pending"
            # 🔴 fixed finder’s fee: ₱200 per booking
            booking.finders_fee = Decimal("200")
            booking.save()
            return redirect("my_bookings")
    else:
        form = BookingForm()

    return render(
        request,
        "installations/book_installation.html",
        {"form": form},
    )


@login_required
def my_bookings(request):
    profile = getattr(request.user, "profile", None)
    # primarily for customers, but we just show "my bookings" to whoever
    bookings = (
        Booking.objects.filter(customer=request.user)
        .select_related("installer", "product")
        .order_by("-created_at")
    )

    return render(
        request,
        "installations/my_bookings.html",
        {"bookings": bookings},
    )

@login_required
def installer_bookings(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.account_type != "installer":
        return redirect("product_list")

    # Handle accept/reject actions
    if request.method == "POST":
        booking_id = request.POST.get("booking_id")
        action = request.POST.get("action")
        booking = get_object_or_404(
            Booking,
            id=booking_id,
            installer=request.user,
        )
        if action == "accept":
            booking.status = "accepted"
        elif action == "reject":
            booking.status = "rejected"
        booking.save()
        return redirect("installer_bookings")

    bookings = (
        Booking.objects.filter(installer=request.user)
        .select_related("customer", "product")
        .order_by("-created_at")
    )

    return render(
        request,
        "installations/installer_bookings.html",
        {"bookings": bookings},
    )

def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            account_type = form.cleaned_data["account_type"]

            Profile.objects.create(user=user, account_type=account_type)
            login(request, user)

            # ✅ Different landing page for seller vs customer
                        # ✅ Different landing page by role
            if account_type == "seller":
                return redirect("seller_dashboard")
            elif account_type == "installer":
                return redirect("installer_dashboard")
            else:
                return redirect("product_list")

    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})

@login_required
def installer_dashboard(request):
    profile = getattr(request.user, "profile", None)
    if not profile or profile.account_type != "installer":
        return redirect("product_list")

    # All bookings for this installer
    bookings_qs = (
        Booking.objects
        .filter(installer=request.user)
        .select_related("customer", "product")
        .order_by("-created_at")
    )

    total_bookings = bookings_qs.count()
    pending_count = bookings_qs.filter(status="pending").count()
    accepted_count = bookings_qs.filter(status="accepted").count()
    rejected_count = bookings_qs.filter(status="rejected").count()

    # Total finder’s fee from accepted bookings
    total_finders_fee = Decimal("0")
    for b in bookings_qs.filter(status="accepted"):
        total_finders_fee += b.finders_fee

    # Upcoming schedule (today onwards, pending or accepted)
    today = timezone.localdate()
    upcoming = (
        bookings_qs
        .filter(status__in=["pending", "accepted"], scheduled_date__gte=today)
        .order_by("scheduled_date", "scheduled_time")[:10]
    )

    context = {
        "total_bookings": total_bookings,
        "pending_count": pending_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "total_finders_fee": total_finders_fee,
        "upcoming": upcoming,
    }
    return render(request, "installations/installer_dashboard.html", context)


# SMALL HELPER FOR SELLER-ONLY VIEWS
def _require_seller(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not hasattr(request.user, "profile") or request.user.profile.account_type != "seller":
        return redirect("product_list")
    return None


# 🟪 SELLER: LIST THEIR OWN PRODUCTS
@login_required
def seller_product_list(request):
    redirect_resp = _require_seller(request)
    if redirect_resp:
        return redirect_resp

    products = Product.objects.filter(seller=request.user).order_by("name")
    return render(request, "seller/seller_product_list.html", {"products": products})


# 🟪 SELLER: CREATE PRODUCT
@login_required
def seller_product_create(request):
    redirect_resp = _require_seller(request)
    if redirect_resp:
        return redirect_resp

    if request.method == "POST":
        form = SellerProductForm(request.POST, request.FILES)  # 👈 include FILES
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            return redirect("seller_product_list")
    else:
        form = SellerProductForm()

    return render(
        request,
        "seller/seller_product_form.html",
        {"form": form, "title": "Add Product"},
    )


# 🟪 SELLER: UPDATE PRODUCT
@login_required
def seller_product_update(request, pk):
    redirect_resp = _require_seller(request)
    if redirect_resp:
        return redirect_resp

    product = get_object_or_404(Product, pk=pk, seller=request.user)

    if request.method == "POST":
        form = SellerProductForm(request.POST, request.FILES, instance=product)  # 👈 include FILES
        if form.is_valid():
            form.save()
            return redirect("seller_product_list")
    else:
        form = SellerProductForm(instance=product)

    return render(
        request,
        "seller/seller_product_form.html",
        {"form": form, "title": "Edit Product"},
    )

# 🟪 SELLER: DELETE PRODUCT
@login_required
def seller_product_delete(request, pk):
    redirect_resp = _require_seller(request)
    if redirect_resp:
        return redirect_resp

    product = get_object_or_404(Product, pk=pk, seller=request.user)

    if request.method == "POST":
        product.delete()
        return redirect("seller_product_list")

    return redirect("seller_product_list")

# 🟪 SELLER: ADD STOCK (quick action)
@login_required
def seller_add_stock(request, pk):
    redirect_resp = _require_seller(request)
    if redirect_resp:
        return redirect_resp

    product = get_object_or_404(Product, pk=pk, seller=request.user)

    if request.method == "POST":
        try:
            add_qty = int(request.POST.get("add_quantity", 0))
        except ValueError:
            add_qty = 0

        if add_qty > 0:
            product.stock = product.stock + add_qty
            product.save()

        # even if invalid value, just go back quietly
        return redirect("seller_product_list")

    # no GET page; just go back
    return redirect("seller_product_list")

from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.decorators import login_required

@login_required
def seller_dashboard(request):
    redirect_resp = _require_seller(request)
    if redirect_resp:
        return redirect_resp

    # all products of this seller
    products = Product.objects.filter(seller=request.user)

    # all order items that belong to this seller's products
    order_items = (
        OrderItem.objects
        .filter(product__seller=request.user)
        .select_related("order", "product")
        .order_by("-order__created_at")
    )

    total_revenue = Decimal("0")
    total_units = 0
    order_ids = set()

    for item in order_items:
        total_revenue += item.unit_price * item.quantity
        total_units += item.quantity
        order_ids.add(item.order_id)

    total_orders = len(order_ids)
    avg_per_order = total_revenue / total_orders if total_orders > 0 else Decimal("0")

    # ---- last 30 days summary ----
    now = timezone.now()
    start_30 = now - timedelta(days=30)
    rev_30 = Decimal("0")
    units_30 = 0

    for item in order_items:
        if item.order.created_at >= start_30:
            rev_30 += item.unit_price * item.quantity
            units_30 += item.quantity

    # ---- top products (by quantity sold) ----
    product_stats = {}
    for item in order_items:
        key = item.product_name
        if key not in product_stats:
            product_stats[key] = {"qty": 0, "revenue": Decimal("0")}
        product_stats[key]["qty"] += item.quantity
        product_stats[key]["revenue"] += item.unit_price * item.quantity

    sorted_products = sorted(
        product_stats.items(),
        key=lambda kv: kv[1]["qty"],
        reverse=True
    )[:5]

    top_products = [
        {"name": name, "qty": data["qty"], "revenue": data["revenue"]}
        for name, data in sorted_products
    ]

    # ---- low stock products ----
    low_stock = products.filter(stock__lte=3).order_by("stock")

    # ---- BADGE LOGIC (based on lifetime revenue) ----
    THRESH_VERIFIED = Decimal("10000")    # ₱10,000
    THRESH_TOP = Decimal("100000")        # ₱100,000

    if total_revenue >= THRESH_TOP:
        badge_level = "top"
        badge_label = "🏆 Top Store"
        next_badge_label = None
        amount_to_next = Decimal("0")
        progress_to_next = 100
    elif total_revenue >= THRESH_VERIFIED:
        badge_level = "verified"
        badge_label = "✅ Verified Store"
        next_badge_label = "🏆 Top Store"
        amount_to_next = max(THRESH_TOP - total_revenue, Decimal("0"))
        # progress within the band 10k–100k
        band_current = max(total_revenue - THRESH_VERIFIED, Decimal("0"))
        band_total = THRESH_TOP - THRESH_VERIFIED  # 90k
        progress_to_next = int(min((band_current / band_total) * 100, 100))
    else:
        badge_level = "none"
        badge_label = "No badge yet"
        next_badge_label = "✅ Verified Store"
        amount_to_next = max(THRESH_VERIFIED - total_revenue, Decimal("0"))
        progress_to_next = int(min((total_revenue / THRESH_VERIFIED) * 100, 100))

    context = {
        "total_revenue": total_revenue,
        "total_units": total_units,
        "total_orders": total_orders,
        "avg_per_order": avg_per_order,
        "rev_30": rev_30,
        "units_30": units_30,
        "top_products": top_products,
        "low_stock": low_stock,

        # badge context
        "badge_level": badge_level,
        "badge_label": badge_label,
        "next_badge_label": next_badge_label,
        "amount_to_next": amount_to_next,
        "progress_to_next": progress_to_next,
    }
    return render(request, "seller/dashboard.html", context)

