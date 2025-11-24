from django import forms
from .models import Product, Booking
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Product


class SignUpForm(UserCreationForm):
    ACCOUNT_CHOICES = (
        ("customer", "Customer"),
        ("seller", "Seller"),
        ("installer", "Installer / Service Provider"),
    )

    account_type = forms.ChoiceField(
        choices=ACCOUNT_CHOICES,
        widget=forms.RadioSelect,
        label="I am signing up as",
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2", "account_type")


class SellerProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "brand", "model", "compatible_years", "price", "stock", "image"]

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            "installer",
            "car_brand",
            "car_model",
            "car_year",
            "scheduled_date",
            "scheduled_time",
        ]
        widgets = {
            "scheduled_date": forms.DateInput(
                attrs={
                    "type": "date",      # 👈 this makes the calendar appear
                }
            ),
            "scheduled_time": forms.TimeInput(
                attrs={
                    "type": "time",      # 👈 this gives a time picker
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["installer"].queryset = User.objects.filter(
            profile__account_type="installer"
        )



