"""
URL configuration for pitstop project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from products.views import product_list, signup

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # main customer product list
    path("", product_list, name="product_list"),

    # your products app (add_to_cart, view_cart, etc.)
    path("products/", include("products.urls")),

    # auth: login/logout/password reset etc.
    path("accounts/", include("django.contrib.auth.urls")),

    # signup
    path("accounts/signup/", signup, name="signup"),

    path("accounts/", include("django.contrib.auth.urls")),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)