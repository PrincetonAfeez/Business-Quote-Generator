import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory

from quotes.admin import QuoteAdmin, QuoteLineItemAdmin, QuoteLineItemInline
from quotes.models import ActivityEvent, Quote, QuoteLineItem


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("admin", "admin@example.com", "pass12345")


@pytest.fixture
def admin_request(admin_user):
    request = RequestFactory().get("/admin/")
    request.user = admin_user
    return request


class TestQuoteLineItemInline:
    def test_locked_quote_disallows_add(self, admin_request, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        inline = QuoteLineItemInline(Quote, AdminSite())
        assert inline.has_add_permission(admin_request, quote) is False

    def test_draft_quote_allows_add(self, admin_request, make_quote):
        inline = QuoteLineItemInline(Quote, AdminSite())
        assert inline.has_add_permission(admin_request, make_quote()) is True

    def test_locked_quote_makes_fields_readonly(self, admin_request, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        inline = QuoteLineItemInline(Quote, AdminSite())
        readonly = inline.get_readonly_fields(admin_request, quote)
        assert "description" in readonly
        assert "quantity" in readonly


class TestQuoteAdmin:
    def test_non_draft_adds_header_fields_to_readonly(self, admin_request, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        admin = QuoteAdmin(Quote, AdminSite())
        readonly = admin.get_readonly_fields(admin_request, quote)
        assert "client" in readonly
        assert "tax_rate" in readonly
        assert "total" in readonly


class TestQuoteLineItemAdmin:
    def test_cannot_change_line_on_sent_quote(self, admin_request, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        item = QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=1)
        admin = QuoteLineItemAdmin(QuoteLineItem, AdminSite())
        assert admin.has_change_permission(admin_request, item) is False
        assert admin.has_delete_permission(admin_request, item) is False
