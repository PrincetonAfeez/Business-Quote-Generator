""" Test models for the quotes app """

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from quotes.models import (
    ActivityEvent,
    CatalogItem,
    Client,
    CompanyProfile,
    InvalidTransition,
    Quote,
    QuoteCounter,
    QuoteLineItem,
    money,
    normalized_validity_days,
)


class TestMoneyHelpers:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, Decimal("0.00")),
            (0, Decimal("0.00")),
            ("10.555", Decimal("10.56")),
            (Decimal("10.554"), Decimal("10.55")),
            (Decimal("10.555"), Decimal("10.56")),
        ],
    )
    def test_money_quantizes_half_up(self, value, expected):
        assert money(value) == expected

    @pytest.mark.parametrize(
        "days,fallback,expected",
        [
            (None, 30, 30),
            (0, 30, 1),
            (-5, 30, 1),
            (14, 30, 14),
        ],
    )
    def test_normalized_validity_days(self, days, fallback, expected):
        assert normalized_validity_days(days, fallback=fallback) == expected


class TestOwnedManager:
    def test_unauthenticated_user_gets_empty_queryset(self, db):
        assert Client.objects.for_user(None).count() == 0

    def test_for_user_scopes_to_owner(self, user, other_user, client_record, other_client):
        assert list(Client.objects.for_user(user)) == [client_record]
        assert list(Client.objects.for_user(other_user)) == [other_client]


class TestClientModel:
    def test_str_prefers_company(self, client_record):
        assert str(client_record) == "Analytical Works"

    def test_str_falls_back_to_name(self, user):
        client = Client.objects.create(owner=user, name="Solo", company="")
        assert str(client) == "Solo"

    def test_to_dict_includes_core_fields(self, client_record):
        payload = client_record.to_dict()
        assert payload["name"] == "Ada Lovelace"
        assert payload["email"] == "ada@example.com"

    def test_clean_lowercases_email(self, user):
        client = Client(owner=user, name="Case", email="  Mixed@Example.COM  ")
        client.clean()
        assert client.email == "mixed@example.com"

    def test_save_persists_lowercase_email(self, user):
        client = Client.objects.create(owner=user, name="Case", email="UPPER@Example.COM")
        assert client.email == "upper@example.com"


class TestCatalogItemModel:
    def test_str_returns_name(self, user):
        item = CatalogItem.objects.create(owner=user, name="Workshop", default_unit_price=Decimal("100.00"))
        assert str(item) == "Workshop"

    def test_to_dict_serializes_price(self, user):
        item = CatalogItem.objects.create(owner=user, name="Workshop", default_unit_price=Decimal("100.00"))
        assert item.to_dict()["default_unit_price"] == "100.00"


class TestCompanyProfileModel:
    def test_str_returns_business_name(self, company_profile):
        assert str(company_profile) == "Northstar Studio"


class TestQuoteCounterModel:
    def test_str_includes_owner_year_and_count(self, user):
        counter = QuoteCounter.objects.create(owner=user, year=2026, last_number=3)
        assert "2026" in str(counter)
        assert "3" in str(counter)


class TestQuoteModel:
    def test_str_before_number_is_unsaved_label(self, user, client_record):
        quote = Quote(owner=user, client=client_record, issue_date=date.today(), expiry_date=date.today() + timedelta(days=30))
        assert str(quote) == "Unsaved quote"

    def test_get_absolute_url(self, make_quote):
        quote = make_quote()
        assert quote.get_absolute_url() == reverse("quotes:quote_detail", args=[quote.pk])

    def test_public_url_empty_without_token(self, make_quote):
        assert make_quote().public_url == ""

    def test_public_url_when_token_set(self, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        assert quote.public_token in quote.public_url

    def test_transition_to_same_status_is_noop(self, make_quote):
        quote = make_quote()
        before = quote.activity_events.count()
        quote.transition_to(Quote.STATUS_DRAFT)
        assert quote.activity_events.count() == before

    def test_transition_sent_to_viewed_to_declined(self, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        quote.transition_to(Quote.STATUS_VIEWED, ActivityEvent.EVENT_VIEWED)
        quote.transition_to(Quote.STATUS_DECLINED, ActivityEvent.EVENT_DECLINED)
        quote.refresh_from_db()
        assert quote.status == Quote.STATUS_DECLINED
        assert quote.declined_at is not None

    def test_transition_draft_to_expired(self, make_quote):
        quote = make_quote()
        quote.transition_to(Quote.STATUS_EXPIRED, ActivityEvent.EVENT_EXPIRED)
        assert quote.status == Quote.STATUS_EXPIRED

    def test_check_expiry_skips_final_statuses(self, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        quote.transition_to(Quote.STATUS_ACCEPTED, ActivityEvent.EVENT_ACCEPTED)
        Quote.objects.filter(pk=quote.pk).update(expiry_date=timezone.localdate() - timedelta(days=1))
        quote.refresh_from_db()
        quote.check_expiry()
        assert quote.status == Quote.STATUS_ACCEPTED

    def test_record_event_defaults_metadata(self, make_quote):
        quote = make_quote()
        quote.record_event(ActivityEvent.EVENT_EDITED)
        event = quote.activity_events.latest("timestamp")
        assert event.metadata == {}

    def test_to_dict_includes_line_items(self, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("10.00"))
        quote.refresh_from_db()
        payload = quote.to_dict()
        assert payload["number"] == quote.number
        assert len(payload["line_items"]) == 1
        assert payload["line_items"][0]["description"] == "Work"

    def test_duplicate_copies_line_items(self, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=2, unit_price=Decimal("50.00"))
        clone = quote.duplicate_for_owner()
        assert clone.line_items.count() == 1
        assert clone.status == Quote.STATUS_DRAFT
        assert clone.activity_events.filter(event_type=ActivityEvent.EVENT_DUPLICATED).exists()

    def test_save_without_owner_raises(self, client_record):
        quote = Quote(client=client_record, issue_date=date.today(), expiry_date=date.today() + timedelta(days=30))
        with pytest.raises(ValidationError):
            quote.save()

    def test_percent_discount_over_100_rejected_on_clean(self, make_quote):
        quote = make_quote()
        quote.discount_type = Quote.DISCOUNT_PERCENT
        quote.discount_value = Decimal("101.00")
        with pytest.raises(ValidationError):
            quote.full_clean()


class TestQuoteLineItemModel:
    def test_str_truncates_description(self, make_quote):
        quote = make_quote()
        item = QuoteLineItem.objects.create(quote=quote, description="x" * 100, quantity=1, unit_price=Decimal("1.00"))
        assert len(str(item)) == 80

    def test_to_dict_serializes_decimals(self, make_quote):
        quote = make_quote()
        item = QuoteLineItem.objects.create(quote=quote, description="Work", quantity=Decimal("2.50"), unit_price=Decimal("10.00"))
        payload = item.to_dict()
        assert payload["quantity"] == "2.50"
        assert payload["line_total"] == "25.00"

    def test_save_updates_parent_quote_total(self, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("100.00"))
        quote.refresh_from_db()
        assert quote.total == Decimal("100.00")

    def test_delete_updates_parent_quote_total(self, make_quote):
        quote = make_quote()
        item = QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("100.00"))
        item.delete()
        quote.refresh_from_db()
        assert quote.total == Decimal("0.00")

    def test_clean_without_quote_id_returns_early(self):
        item = QuoteLineItem(description="Orphan", quantity=1, unit_price=Decimal("1.00"))
        item.clean()

    def test_clean_rejects_missing_quote(self, user):
        item = QuoteLineItem(quote_id=99999, description="Bad", quantity=1, unit_price=Decimal("1.00"))
        with pytest.raises(ValidationError):
            item.full_clean()


class TestActivityEventModel:
    def test_str_includes_quote_number_and_type(self, make_quote):
        quote = make_quote()
        event = ActivityEvent.objects.create(quote=quote, event_type=ActivityEvent.EVENT_CREATED)
        assert quote.number in str(event)
        assert "created" in str(event)


class TestInvalidTransition:
    def test_is_value_error_subclass(self):
        assert issubclass(InvalidTransition, ValueError)
