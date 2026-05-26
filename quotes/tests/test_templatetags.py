""" Test templatetags for the quotes app """

from decimal import Decimal

import pytest
from django.template import Context, Template
from django.test import RequestFactory

from quotes.models import Quote
from quotes.templatetags import quote_extras


class TestCurrencyFilter:
    def test_formats_decimal(self):
        assert quote_extras.currency(Decimal("1234.5")) == "$1,234.50"

    def test_none_becomes_zero(self):
        assert quote_extras.currency(None) == "$0.00"


class TestStatusBadgeFilter:
    @pytest.mark.parametrize(
        "status,token",
        [
            ("draft", "slate"),
            ("sent", "sky"),
            ("viewed", "cyan"),
            ("accepted", "emerald"),
            ("declined", "rose"),
            ("expired", "amber"),
            ("unknown", "slate"),
        ],
    )
    def test_status_badge_classes(self, status, token):
        assert token in quote_extras.status_badge(status)


class TestQuoteHasStatusFilter:
    def test_matches_allowed_statuses(self, make_quote):
        quote = make_quote()
        quote.status = Quote.STATUS_SENT
        quote.save(update_fields=["status", "updated_at"])
        assert quote_extras.quote_has_status(quote, "sent,viewed") is True
        assert quote_extras.quote_has_status(quote, "accepted") is False


class TestDiscountSummaryFilter:
    def test_none_discount(self, make_quote):
        quote = make_quote(discount_type=Quote.DISCOUNT_NONE)
        assert quote_extras.discount_summary(quote) == "None"

    def test_flat_discount(self, make_quote):
        quote = make_quote()
        quote.discount_type = Quote.DISCOUNT_FLAT
        quote.discount_value = Decimal("15.00")
        assert quote_extras.discount_summary(quote) == "$15.00 flat"


class TestQsReplaceTag:
    def test_replaces_and_removes_query_params(self):
        request = RequestFactory().get("/", {"page": "2", "q": "ada"})
        rendered = Template("{% load quote_extras %}{% qs_replace page=3 q=None %}").render(Context({"request": request}))
        assert "page=3" in rendered
        assert "q=" not in rendered


class TestSortLinkTag:
    def test_toggles_direction_for_active_column(self):
        request = RequestFactory().get("/", {"sort": "total", "dir": "desc"})
        rendered = Template("{% load quote_extras %}{% sort_link 'total' 'desc' %}").render(Context({"request": request}))
        assert "dir=asc" in rendered

    def test_resets_page_when_sorting(self):
        request = RequestFactory().get("/", {"sort": "client", "dir": "asc", "page": "3"})
        rendered = Template("{% load quote_extras %}{% sort_link 'total' 'desc' %}").render(Context({"request": request}))
        assert "sort=total" in rendered
        assert "page=" not in rendered


class TestSortIndicatorTag:
    def test_shows_arrow_for_active_column(self):
        request = RequestFactory().get("/", {"sort": "total", "dir": "asc"})
        assert quote_extras.sort_indicator(Context({"request": request}), "total") == "↑"
        assert quote_extras.sort_indicator(Context({"request": request}), "client") == ""


class TestSortAriaTag:
    def test_returns_none_for_inactive_column(self):
        request = RequestFactory().get("/")
        assert quote_extras.sort_aria(Context({"request": request}), "total") == "none"

    def test_returns_direction_for_active_column(self):
        request = RequestFactory().get("/", {"sort": "total", "dir": "desc"})
        assert quote_extras.sort_aria(Context({"request": request}), "total") == "descending"
