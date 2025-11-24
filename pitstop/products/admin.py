from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "model", "price", "stock")
    search_fields = ("name", "brand", "model")
