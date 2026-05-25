from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from quotes.forms import (
    CatalogItemForm,
    ClientForm,
    CompanyProfileForm,
    QuoteCreateForm,
    QuoteForm,
    QuoteLineItemForm,
    SignupForm,
)
from quotes.models import ActivityEvent, CatalogItem, Client, Quote, QuoteLineItem


class TestSignupForm:
    def test_rejects_duplicate_email(self, db):
        User.objects.create_user("existing", email="taken@example.com", password="pass12345")
        form = SignupForm({"username": "new", "email": "taken@example.com", "password1": "complex-pass-12345", "password2": "complex-pass-12345"})
        assert form.is_valid() is False
        assert "email" in form.errors

    def test_applies_tailwind_classes(self, db):
        form = SignupForm()
        assert "rounded-md" in form.fields["username"].widget.attrs.get("class", "")


class TestClientForm:
    def test_rejects_duplicate_email_case_insensitive(self, user, client_record):
        form = ClientForm(
            {"name": "Dup", "company": "", "email": "ADA@example.com", "phone": "", "billing_address": "", "notes": ""},
            owner=user,
        )
        assert form.is_valid() is False

    def test_allows_blank_email(self, user):
        form = ClientForm(
            {"name": "No Email", "company": "", "email": "", "phone": "", "billing_address": "", "notes": ""},
            owner=user,
        )
        assert form.is_valid(), form.errors

    def test_save_assigns_owner(self, user):
        form = ClientForm(
            {"name": "New", "company": "", "email": "new@example.com", "phone": "", "billing_address": "", "notes": ""},
            owner=user,
        )
        assert form.is_valid(), form.errors
        client = form.save()
        assert client.owner_id == user.id
        assert client.email == "new@example.com"


class TestCatalogItemForm:
    def test_valid_catalog_item(self, user):
        form = CatalogItemForm(
            {"name": "SKU", "description": "Desc", "default_unit_price": "10.00", "unit": "each"},
            owner=user,
        )
        assert form.is_valid(), form.errors
        item = form.save()
        assert item.owner_id == user.id


class TestCompanyProfileForm:
    def test_valid_profile(self, company_profile):
        form = CompanyProfileForm(
            {"business_name": "Updated", "address": "", "tax_id": "", "default_tax_rate": "0.00", "default_terms": "", "default_validity_days": "30"},
            instance=company_profile,
        )
        assert form.is_valid(), form.errors


class TestQuoteForm:
    def test_client_queryset_scoped_to_owner(self, user, other_user, client_record, other_client, make_quote):
        quote = make_quote()
        form = QuoteForm(instance=quote, owner=user)
        assert other_client not in form.fields["client"].queryset

    def test_save_recalculates_totals(self, user, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("100.00"))
        form = QuoteForm(
            {
                "client": quote.client_id,
                "issue_date": quote.issue_date.isoformat(),
                "expiry_date": quote.expiry_date.isoformat(),
                "tax_rate": "10.00",
                "discount_type": Quote.DISCOUNT_NONE,
                "discount_value": "0.00",
                "notes": "",
                "terms": "",
                "is_favorite": False,
            },
            instance=quote,
            owner=user,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.tax_rate == Decimal("10.00")


class TestQuoteCreateForm:
    def test_invalid_without_client(self, user):
        form = QuoteCreateForm({}, owner=user)
        assert form.is_valid() is False


class TestQuoteLineItemForm:
    def test_catalog_item_prefills_description_and_price(self, user):
        catalog = CatalogItem.objects.create(owner=user, name="Workshop", description="Facilitation", default_unit_price=Decimal("250.00"))
        form = QuoteLineItemForm({"catalog_item": catalog.pk, "quantity": "1", "unit_price": "250.00", "position": "1"}, owner=user)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["description"] == "Facilitation"

    def test_requires_description_or_catalog(self, user):
        form = QuoteLineItemForm({"quantity": "1", "unit_price": "10.00", "position": "1"}, owner=user)
        assert form.is_valid() is False

    def test_rejects_zero_quantity(self, user):
        form = QuoteLineItemForm({"description": "Work", "quantity": "0", "unit_price": "10.00", "position": "1"}, owner=user)
        assert form.is_valid() is False
        assert "quantity" in form.errors

    def test_catalog_queryset_scoped(self, user, other_user):
        CatalogItem.objects.create(owner=other_user, name="Other", default_unit_price=Decimal("1.00"))
        own = CatalogItem.objects.create(owner=user, name="Mine", default_unit_price=Decimal("1.00"))
        form = QuoteLineItemForm(owner=user)
        assert own in form.fields["catalog_item"].queryset
        assert form.fields["catalog_item"].queryset.count() == 1
