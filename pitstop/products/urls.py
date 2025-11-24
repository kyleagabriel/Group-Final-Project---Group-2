from django.urls import path
from . import views

urlpatterns = [
    # customer side
    path("", views.product_list, name="product_list"),
    path("cart/", views.view_cart, name="view_cart"),
    path("transactions/", views.transaction_history, name="transaction_history"),
    path("add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("detail/<int:pk>/", views.product_detail, name="product_detail"),

    # 🔹 mock payment + order tracking (RESTORED)
    path("payment/", views.mock_payment, name="mock_payment"),
    path("track/<int:order_id>/", views.track_order, name="track_order"),

    # installation / bookings (customer + installer)
    path("install/book/", views.book_installation, name="book_installation"),
    path("install/my-bookings/", views.my_bookings, name="my_bookings"),

    # installer side
    path("installer/dashboard/", views.installer_dashboard, name="installer_dashboard"),
    path("installer/bookings/", views.installer_bookings, name="installer_bookings"),

    # seller side
    path("seller/dashboard/", views.seller_dashboard, name="seller_dashboard"),
    path("seller/products/", views.seller_product_list, name="seller_product_list"),
    path("seller/products/add/", views.seller_product_create, name="seller_product_create"),
    path("seller/products/<int:pk>/add-stock/",views.seller_add_stock,name="seller_add_stock",),
    path("seller/products/<int:pk>/edit/", views.seller_product_update, name="seller_product_update"),
    path("seller/products/<int:pk>/delete/", views.seller_product_delete, name="seller_product_delete"),
]
