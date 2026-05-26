""" Forms for the quotes app """

from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import ActivityEvent, CatalogItem, Client, CompanyProfile, Quote, QuoteLineItem, normalized_validity_days


CONTROL_CLASS = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-100"


class TailwindFormMixin:
    def apply_control_classes(self):
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {CONTROL_CLASS}".strip()


class SignupForm(TailwindFormMixin, UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class CompanyProfileForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ("business_name", "logo", "address", "tax_id", "default_tax_rate", "default_terms", "default_validity_days")
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "default_terms": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_control_classes()


class OwnerFilteredModelForm(TailwindFormMixin, forms.ModelForm):
    owner = None

    def __init__(self, *args, owner=None, **kwargs):
        self.owner = owner
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

    def _post_clean(self):
        if self.owner and self.instance is not None and not self.instance.owner_id:
            self.instance.owner = self.owner
        super()._post_clean()

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.owner and not instance.pk:
            instance.owner = self.owner
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ClientForm(OwnerFilteredModelForm):
    class Meta:
        model = Client
        fields = ("name", "company", "email", "phone", "billing_address", "notes")
        widgets = {
            "billing_address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            return email
        qs = Client.objects.filter(owner=self.owner, email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A client with this email already exists.")
        return email


class CatalogItemForm(OwnerFilteredModelForm):
    class Meta:
        model = CatalogItem
        fields = ("name", "description", "default_unit_price", "unit")
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class QuoteForm(OwnerFilteredModelForm):
    class Meta:
        model = Quote
        fields = ("client", "issue_date", "expiry_date", "tax_rate", "discount_type", "discount_value", "notes", "terms", "is_favorite")
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "terms": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, owner=owner, **kwargs)
        self.fields["client"].queryset = Client.objects.for_user(owner)
        if self.instance and self.instance.pk:
            self.fields["client"].disabled = True
            self.fields["client"].help_text = "Client cannot be changed after the quote is created."

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.owner and not instance.pk:
            instance.owner = self.owner
        if commit:
            instance.save()
            instance.calculate_totals(save=True)
            self.save_m2m()
        return instance


class QuoteCreateForm(TailwindFormMixin, forms.Form):
    client = forms.ModelChoiceField(queryset=Client.objects.none())

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.fields["client"].queryset = Client.objects.for_user(owner)
        self.apply_control_classes()

    def save(self):
        profile = CompanyProfile.objects.for_user(self.owner).first()
        issue_date = timezone.localdate()
        validity_days = normalized_validity_days(profile.default_validity_days if profile else 30)
        quote = Quote.objects.create(
            owner=self.owner,
            client=self.cleaned_data["client"],
            issue_date=issue_date,
            expiry_date=issue_date + timedelta(days=validity_days),
            tax_rate=profile.default_tax_rate if profile else 0,
            terms=profile.default_terms if profile else "",
        )
        quote.record_event(ActivityEvent.EVENT_CREATED)
        return quote


class QuoteLineItemForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = QuoteLineItem
        fields = ("catalog_item", "description", "quantity", "unit_price", "position")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "position": forms.HiddenInput(),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["catalog_item"].queryset = CatalogItem.objects.for_user(owner)
        self.fields["catalog_item"].required = False
        self.fields["description"].required = False
        self.apply_control_classes()

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("catalog_item")
        if item:
            if not cleaned.get("description"):
                cleaned["description"] = item.description or item.name
            if cleaned.get("unit_price") is None:
                cleaned["unit_price"] = item.default_unit_price
        if not cleaned.get("description"):
            raise forms.ValidationError("Add a description or pick a catalog item.")
        quantity = cleaned.get("quantity")
        unit_price = cleaned.get("unit_price")
        if quantity is not None and quantity < Decimal("0.01"):
            self.add_error("quantity", "Quantity must be greater than zero.")
        if unit_price is not None and unit_price < Decimal("0"):
            self.add_error("unit_price", "Unit price cannot be negative.")
        return cleaned
