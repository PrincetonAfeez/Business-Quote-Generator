from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ActivityEvent, CatalogItem, Client, CompanyProfile, InvalidTransition, Quote, QuoteLineItem


class QuoteTestMixin:
    def setUp(self):
        self.user = User.objects.create_user("owner", password="pass12345")
        self.other = User.objects.create_user("other", password="pass12345")
        self.client_record = Client.objects.create(owner=self.user, name="Ada Lovelace", company="Analytical Works", email="ada@example.com")
        self.other_client = Client.objects.create(owner=self.other, name="Grace Hopper")
        CompanyProfile.objects.create(owner=self.user, business_name="Northstar Studio", default_tax_rate=Decimal("8.25"), default_terms="Due on receipt")

    def make_quote(self, **kwargs):
        today = timezone.localdate()
        defaults = {
            "owner": self.user,
            "client": self.client_record,
            "issue_date": today,
            "expiry_date": today + timedelta(days=30),
            "tax_rate": Decimal("0.00"),
        }
        defaults.update(kwargs)
        quote = Quote.objects.create(**defaults)
        quote.record_event(ActivityEvent.EVENT_CREATED)
        return quote


class MoneyAndModelTests(QuoteTestMixin, TestCase):
    def test_owned_manager_filters_by_user(self):
        Quote.objects.create(owner=self.other, client=self.other_client, issue_date=date(2026, 1, 5), expiry_date=date(2026, 2, 4))
        quote = self.make_quote()
        self.assertEqual(list(Quote.objects.for_user(self.user)), [quote])

    def test_totals_use_decimal_and_tax_after_discount(self):
        quote = self.make_quote(tax_rate=Decimal("10.00"), discount_type=Quote.DISCOUNT_PERCENT, discount_value=Decimal("25.00"))
        QuoteLineItem.objects.create(quote=quote, description="Strategy", quantity=Decimal("2.00"), unit_price=Decimal("100.00"))
        quote.refresh_from_db()
        quote.calculate_totals(save=True)

        self.assertEqual(quote.subtotal, Decimal("200.00"))
        self.assertEqual(quote.discount_amount, Decimal("50.00"))
        self.assertEqual(quote.tax_amount, Decimal("15.00"))
        self.assertEqual(quote.total, Decimal("165.00"))

    def test_total_rounding_boundary_cases(self):
        quote = self.make_quote(tax_rate=Decimal("0.00"))
        QuoteLineItem.objects.create(quote=quote, description="Rounding", quantity=Decimal("1.00"), unit_price=Decimal("0.015"))
        quote.refresh_from_db()
        self.assertEqual(quote.total, Decimal("0.02"))

        quote.discount_type = Quote.DISCOUNT_PERCENT
        quote.discount_value = Decimal("100.00")
        quote.calculate_totals(save=True)
        self.assertEqual(quote.total, Decimal("0.00"))

    def test_negative_discount_is_rejected(self):
        quote = self.make_quote(discount_type=Quote.DISCOUNT_FLAT, discount_value=Decimal("-1.00"))
        with self.assertRaises(ValueError):
            quote.calculate_totals()

    def test_quote_numbering_is_per_user_and_per_year(self):
        q1 = self.make_quote(issue_date=date(2026, 1, 1))
        q2 = self.make_quote(issue_date=date(2026, 1, 2))
        q3 = self.make_quote(issue_date=date(2027, 1, 1))
        other = Quote.objects.create(owner=self.other, client=self.other_client, issue_date=date(2026, 1, 1), expiry_date=date(2026, 2, 1))

        self.assertEqual(q1.number, "Q-2026-0001")
        self.assertEqual(q2.number, "Q-2026-0002")
        self.assertEqual(q3.number, "Q-2027-0001")
        self.assertEqual(other.number, "Q-2026-0001")

    def test_public_token_is_unique_url_safe_and_32_chars(self):
        q1 = self.make_quote()
        q2 = self.make_quote()
        self.assertEqual(len(q1.ensure_public_token()), 32)
        self.assertNotEqual(q1.public_token, q2.ensure_public_token())
        self.assertTrue(q1.public_token.isalnum())

    def test_status_transitions_record_activity_and_reject_invalid(self):
        quote = self.make_quote()
        with self.assertRaises(InvalidTransition):
            quote.transition_to(Quote.STATUS_ACCEPTED)

        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        quote.transition_to(Quote.STATUS_VIEWED, ActivityEvent.EVENT_VIEWED)
        quote.transition_to(Quote.STATUS_ACCEPTED, ActivityEvent.EVENT_ACCEPTED)
        quote.refresh_from_db()

        self.assertEqual(quote.status, Quote.STATUS_ACCEPTED)
        self.assertIsNotNone(quote.accepted_at)
        self.assertEqual(quote.activity_events.filter(event_type=ActivityEvent.EVENT_ACCEPTED).count(), 1)

    def test_lazy_expiry_marks_open_quote_expired(self):
        quote = self.make_quote(expiry_date=timezone.localdate() - timedelta(days=1))
        quote.check_expiry()
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_EXPIRED)


class ViewTests(QuoteTestMixin, TestCase):
    def test_auth_required_for_quote_list(self):
        response = self.client.get(reverse("quotes:quote_list"))
        self.assertEqual(response.status_code, 302)

    def test_cross_user_quote_detail_is_forbidden(self):
        quote = Quote.objects.create(owner=self.other, client=self.other_client, issue_date=date(2026, 1, 5), expiry_date=date(2026, 2, 4))
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("quotes:quote_detail", args=[quote.pk]))
        self.assertEqual(response.status_code, 403)

    def test_same_url_returns_json_when_requested(self):
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("quotes:quote_detail", args=[quote.pk]), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["number"], quote.number)

    def test_hx_quote_list_returns_partial_with_oob(self):
        self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("quotes:quote_list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hx-swap-oob")
        self.assertNotContains(response, "<html")

    def test_hx_mutation_sets_trigger_header(self):
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(reverse("quotes:quote_toggle_favorite", args=[quote.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertIn("show-toast", response.headers["HX-Trigger"])

    def test_public_quote_view_without_auth_marks_viewed(self):
        quote = self.make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)

        response = self.client.get(reverse("quotes:public_quote", args=[quote.public_token]))
        self.assertEqual(response.status_code, 200)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_VIEWED)
        self.assertIsNotNone(quote.viewed_at)

    def test_public_accept_writes_audit_metadata(self):
        quote = self.make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        quote.transition_to(Quote.STATUS_VIEWED, ActivityEvent.EVENT_VIEWED)

        response = self.client.post(reverse("quotes:public_quote", args=[quote.public_token]), {"action": "accept"}, HTTP_HX_REQUEST="true", HTTP_USER_AGENT="Tests")
        self.assertEqual(response.status_code, 200)
        quote.refresh_from_db()
        event = quote.activity_events.get(event_type=ActivityEvent.EVENT_ACCEPTED)
        self.assertEqual(quote.status, Quote.STATUS_ACCEPTED)
        self.assertIn("user_agent", event.metadata)

    def test_pdf_generation_smoke(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Build", quantity=1, unit_price=100)
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("quotes:quote_pdf", args=[quote.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_line_item_hx_response_contains_oob_totals(self):
        item = CatalogItem.objects.create(owner=self.user, name="Workshop", description="Facilitated workshop", default_unit_price=Decimal("250.00"))
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(
            reverse("quotes:line_item_add", args=[quote.pk]),
            {"catalog_item": item.pk, "quantity": "1", "unit_price": "250.00", "position": "1"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "grand-total-panel")
        self.assertContains(response, "hx-swap-oob")
