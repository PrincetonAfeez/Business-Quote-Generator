from datetime import timedelta

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import CatalogItem, Client, CompanyProfile, Quote, QuoteLineItem


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

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.owner and not instance.pk:
            instance.owner = self.owner
        if commit:
            instance.full_clean()
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
        validity_days = profile.default_validity_days if profile else 30
        quote = Quote.objects.create(
            owner=self.owner,
            client=self.cleaned_data["client"],
            issue_date=issue_date,
            expiry_date=issue_date + timedelta(days=validity_days),
            tax_rate=profile.default_tax_rate if profile else 0,
            terms=profile.default_terms if profile else "",
        )
        quote.record_event("created")
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
            if not cleaned.get("unit_price"):
                cleaned["unit_price"] = item.default_unit_price
        if not cleaned.get("description"):
            raise forms.ValidationError("Add a description or pick a catalog item.")
        return cleaned
