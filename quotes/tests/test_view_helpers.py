import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from quotes.models import ActivityEvent, CatalogItem, Client, CompanyProfile, Quote, QuoteLineItem
from quotes.views import (
    add_toast,
    build_quote_detail_context,
    can_send_quote,
    client_ip,
    draft_quotes_for,
    favorite_count,
    forbidden_if_not_owner,
    is_hx,
    is_probable_bot,
    profile_for,
    quote_is_editable,
    quote_queryset_from_request,
    wants_json,
    _parse_iso_date,
)


@pytest.fixture
def rf():
    return RequestFactory()


class TestRequestHelpers:
    def test_is_hx_true_when_header_set(self, rf):
        request = rf.get("/", HTTP_HX_REQUEST="true")
        assert is_hx(request) is True

    def test_is_hx_false_without_header(self, rf):
        assert is_hx(rf.get("/")) is False

    def test_wants_json_requires_accept_and_not_hx(self, rf):
        request = rf.get("/", HTTP_ACCEPT="application/json")
        assert wants_json(request) is True
        assert wants_json(rf.get("/", HTTP_ACCEPT="application/json", HTTP_HX_REQUEST="true")) is False

    def test_add_toast_sets_hx_trigger(self):
        response = add_toast(HttpResponse(), "Saved", "success")
        payload = json.loads(response["HX-Trigger"])
        assert payload["show-toast"]["message"] == "Saved"
        assert payload["show-toast"]["level"] == "success"


class TestOwnershipHelpers:
    def test_forbidden_if_not_owner_quote(self, user, other_user, other_client):
        quote = Quote.objects.create(
            owner=other_user,
            client=other_client,
            issue_date=timezone.localdate(),
            expiry_date=timezone.localdate() + timedelta(days=30),
        )
        with pytest.raises(PermissionDenied):
            forbidden_if_not_owner(quote, user)

    def test_forbidden_if_not_owner_client(self, user, other_client):
        with pytest.raises(PermissionDenied):
            forbidden_if_not_owner(other_client, user)

    def test_forbidden_if_not_owner_line_item(self, user, other_user, other_client):
        quote = Quote.objects.create(
            owner=other_user,
            client=other_client,
            issue_date=timezone.localdate(),
            expiry_date=timezone.localdate() + timedelta(days=30),
        )
        item = QuoteLineItem.objects.create(quote=quote, description="X", quantity=1, unit_price=Decimal("1.00"))
        with pytest.raises(PermissionDenied):
            forbidden_if_not_owner(item, user)

    def test_forbidden_if_not_owner_returns_object(self, user, client_record):
        assert forbidden_if_not_owner(client_record, user) is client_record


class TestQuoteWorkflowHelpers:
    def test_quote_is_editable_draft(self, make_quote):
        assert quote_is_editable(make_quote()) is True

    def test_quote_is_editable_sent_is_false(self, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        assert quote_is_editable(quote) is False

    def test_quote_is_editable_archived_is_false(self, make_quote):
        quote = make_quote()
        quote.archived_at = quote.updated_at
        quote.save(update_fields=["archived_at", "updated_at"])
        assert quote_is_editable(quote) is False

    def test_can_send_quote_requires_email_and_lines(self, make_quote, user):
        quote = make_quote()
        assert can_send_quote(quote) is False
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        assert can_send_quote(quote) is True

    def test_can_send_quote_false_when_archived(self, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.archived_at = quote.updated_at
        quote.save(update_fields=["archived_at", "updated_at"])
        assert can_send_quote(quote) is False

    def test_can_send_resend_when_sent_without_token(self, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        quote.public_token = None
        quote.save(update_fields=["public_token", "updated_at"])
        assert can_send_quote(quote) is True

    def test_build_quote_detail_context_keys(self, rf, user, make_quote, company_profile):
        quote = make_quote()
        request = rf.get("/")
        request.user = user
        context = build_quote_detail_context(request, quote)
        assert {"quote", "form", "line_form", "can_send_quote", "quote_is_editable"} <= context.keys()


class TestUtilityHelpers:
    def test_favorite_count_excludes_archived(self, user, make_quote):
        active = make_quote(is_favorite=True)
        archived = make_quote(is_favorite=True)
        archived.archived_at = archived.updated_at
        archived.save(update_fields=["archived_at", "updated_at"])
        assert favorite_count(user) == 1
        assert active.is_favorite

    def test_profile_for_missing_returns_none(self, user):
        CompanyProfile.objects.filter(owner=user).delete()
        assert profile_for(user) is None

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("", None),
            (None, None),
            ("2026-05-01", date(2026, 5, 1)),
            ("bad", None),
        ],
    )
    def test_parse_iso_date(self, value, expected):
        assert _parse_iso_date(value) == expected

    def test_client_ip_uses_forwarded_for(self, rf):
        request = rf.get("/", HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1")
        assert client_ip(request) == "203.0.113.1"

    def test_client_ip_falls_back_to_remote_addr(self, rf):
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        assert client_ip(request) == "127.0.0.1"

    @pytest.mark.parametrize(
        "user_agent,is_bot",
        [
            ("Mozilla/5.0 Chrome", False),
            ("Slackbot-LinkExpanding 1.0", True),
            ("Twitterbot/1.0", True),
            ("Googlebot/2.1", True),
        ],
    )
    def test_is_probable_bot(self, rf, user_agent, is_bot):
        request = rf.get("/", HTTP_USER_AGENT=user_agent)
        assert is_probable_bot(request) is is_bot


class TestQuoteQueryset:
    def test_quote_queryset_search_filter(self, rf, user, make_quote, client_record):
        make_quote()
        request = rf.get("/", {"q": "Ada"})
        request.user = user
        assert quote_queryset_from_request(request).count() == 1

    def test_quote_queryset_favorites_filter(self, rf, user, make_quote):
        make_quote(is_favorite=True)
        make_quote(is_favorite=False)
        request = rf.get("/", {"favorites": "1"})
        request.user = user
        assert quote_queryset_from_request(request).count() == 1

    def test_quote_queryset_sort_by_total(self, rf, user, make_quote):
        low = make_quote()
        QuoteLineItem.objects.create(quote=low, description="A", quantity=1, unit_price=Decimal("10.00"))
        high = make_quote()
        QuoteLineItem.objects.create(quote=high, description="B", quantity=1, unit_price=Decimal("100.00"))
        request = rf.get("/", {"sort": "total", "dir": "desc"})
        request.user = user
        results = list(quote_queryset_from_request(request))
        assert results[0].pk == high.pk

    def test_draft_quotes_for_excludes_sent(self, user, make_quote):
        draft = make_quote()
        sent = make_quote()
        sent.ensure_public_token()
        sent.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        ids = list(draft_quotes_for(user).values_list("pk", flat=True))
        assert draft.pk in ids
        assert sent.pk not in ids
