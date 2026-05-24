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
            "tax_rate": Decimal("0.00"),
        }
        defaults.update(kwargs)
        if "expiry_date" not in defaults:
            defaults["expiry_date"] = defaults["issue_date"] + timedelta(days=30)
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


class FailurePathTests(QuoteTestMixin, TestCase):
    def test_send_blocked_when_client_has_no_email(self):
        no_email_client = Client.objects.create(owner=self.user, name="Email-less")
        quote = self.make_quote(client=no_email_client)
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("100.00"))
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(reverse("quotes:quote_send", args=[quote.pk]), follow=True)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_DRAFT)
        self.assertContains(response, "Add an email address")

    def test_send_blocked_when_quote_has_no_line_items(self):
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(reverse("quotes:quote_send", args=[quote.pk]), follow=True)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_DRAFT)
        self.assertContains(response, "at least one line item")

    def test_send_blocked_on_final_status(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("100.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        quote.transition_to(Quote.STATUS_ACCEPTED, ActivityEvent.EVENT_ACCEPTED)
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(reverse("quotes:quote_send", args=[quote.pk]), follow=True)
        self.assertContains(response, "cannot be sent")

    def test_client_delete_protected_when_quote_exists(self):
        self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(reverse("quotes:client_delete", args=[self.client_record.pk]), follow=True)
        self.assertTrue(Client.objects.filter(pk=self.client_record.pk).exists())
        self.assertContains(response, "referenced by existing quotes")

    def test_line_item_form_rejects_negative_values(self):
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(
            reverse("quotes:line_item_add", args=[quote.pk]),
            {"description": "Refund", "quantity": "-1", "unit_price": "10.00", "position": "1"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(quote.line_items.count(), 0)

    def test_line_item_form_rejects_negative_unit_price(self):
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(
            reverse("quotes:line_item_add", args=[quote.pk]),
            {"description": "Discount line", "quantity": "1", "unit_price": "-25.00", "position": "1"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(quote.line_items.count(), 0)

    def test_catalog_item_zero_price_is_preserved(self):
        item = CatalogItem.objects.create(owner=self.user, name="Freebie", description="Free trial", default_unit_price=Decimal("99.00"))
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(
            reverse("quotes:line_item_add", args=[quote.pk]),
            {"catalog_item": item.pk, "description": "Free trial", "quantity": "1", "unit_price": "0.00", "position": "1"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        saved = quote.line_items.get()
        self.assertEqual(saved.unit_price, Decimal("0.00"))

    def test_expiry_before_issue_date_is_rejected(self):
        today = timezone.localdate()
        quote = Quote(
            owner=self.user,
            client=self.client_record,
            issue_date=today,
            expiry_date=today - timedelta(days=1),
        )
        with self.assertRaises(Exception):
            quote.full_clean()

    def test_invalid_date_filter_does_not_crash(self):
        self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("quotes:quote_list"), {"start": "not-a-date", "end": "??", "client": "abc"})
        self.assertEqual(response.status_code, 200)

    def test_finalized_quote_cannot_be_edited(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("50.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        quote.transition_to(Quote.STATUS_ACCEPTED, ActivityEvent.EVENT_ACCEPTED)
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(
            reverse("quotes:line_item_add", args=[quote.pk]),
            {"description": "Sneaky extra", "quantity": "1", "unit_price": "999.00", "position": "2"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(quote.line_items.count(), 1)

    def test_public_pdf_applies_expiry(self):
        quote = self.make_quote(expiry_date=timezone.localdate() - timedelta(days=1))
        QuoteLineItem.objects.create(quote=quote, description="Late", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        response = self.client.get(reverse("quotes:public_quote_pdf", args=[quote.public_token]))
        self.assertEqual(response.status_code, 200)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_EXPIRED)

    def test_duplicated_quote_refreshes_expiry(self):
        today = timezone.localdate()
        quote = self.make_quote(
            issue_date=today - timedelta(days=30),
            expiry_date=today - timedelta(days=1),
        )
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("10.00"))
        clone = quote.duplicate_for_owner()
        self.assertEqual(clone.issue_date, today)
        self.assertGreaterEqual(clone.expiry_date, today)


class ExtendedCoverageTests(QuoteTestMixin, TestCase):
    def test_make_quote_helper_derives_expiry_from_issue_date(self):
        quote = self.make_quote(issue_date=date(2026, 1, 2))
        self.assertEqual(quote.expiry_date, date(2026, 2, 1))

    def test_dashboard_renders_with_aggregates(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("500.00"))
        quote.refresh_from_db()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("quotes:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Outstanding")

    def test_quote_create_redirects_when_no_clients_exist(self):
        Quote.objects.all().delete()
        Client.objects.filter(owner=self.user).delete()
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("quotes:quote_create"))
        self.assertRedirects(response, reverse("quotes:client_create"))

    def test_quote_revoke_public_link(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(reverse("quotes:quote_revoke_public_link", args=[quote.pk]), follow=True)
        quote.refresh_from_db()
        self.assertIsNone(quote.public_token)
        self.assertContains(response, "revoked")

    def test_expiry_equal_to_issue_date_is_rejected(self):
        today = timezone.localdate()
        quote = Quote(owner=self.user, client=self.client_record, issue_date=today, expiry_date=today)
        with self.assertRaises(Exception):
            quote.full_clean()

    def test_flat_discount_exceeding_subtotal_is_rejected(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("100.00"))
        quote.refresh_from_db()
        quote.discount_type = Quote.DISCOUNT_FLAT
        quote.discount_value = Decimal("500.00")
        with self.assertRaises(Exception):
            quote.full_clean()

    def test_quantity_zero_is_rejected(self):
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(
            reverse("quotes:line_item_add", args=[quote.pk]),
            {"description": "Zero", "quantity": "0", "unit_price": "10.00", "position": "1"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(quote.line_items.count(), 0)

    def test_client_email_must_be_unique_per_owner(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Client.objects.create(owner=self.user, name="Ada Duplicate", email="ada@example.com")

    def test_blank_client_emails_can_coexist(self):
        Client.objects.create(owner=self.user, name="No Email A", email="")
        Client.objects.create(owner=self.user, name="No Email B", email="")

    def test_quote_form_freezes_client_after_creation(self):
        from quotes.forms import QuoteForm
        quote = self.make_quote()
        form = QuoteForm(instance=quote, owner=self.user)
        self.assertTrue(form.fields["client"].disabled)

    def test_quote_create_uses_event_constant(self):
        from quotes.forms import QuoteCreateForm
        form = QuoteCreateForm({"client": self.client_record.pk}, owner=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        quote = form.save()
        self.assertEqual(quote.activity_events.first().event_type, ActivityEvent.EVENT_CREATED)

    def test_bot_user_agent_does_not_mark_viewed(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        response = self.client.get(
            reverse("quotes:public_quote", args=[quote.public_token]),
            HTTP_USER_AGENT="Slackbot-LinkExpanding 1.0",
        )
        self.assertEqual(response.status_code, 200)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_SENT)

    def test_real_browser_user_agent_marks_viewed(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        response = self.client.get(
            reverse("quotes:public_quote", args=[quote.public_token]),
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0)",
        )
        self.assertEqual(response.status_code, 200)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_VIEWED)

    def test_x_forwarded_for_captured_in_audit(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        self.client.post(
            reverse("quotes:public_quote", args=[quote.public_token]),
            {"action": "accept"},
            HTTP_HX_REQUEST="true",
            HTTP_USER_AGENT="Mozilla/5.0",
            HTTP_X_FORWARDED_FOR="203.0.113.42, 10.0.0.1",
        )
        event = quote.activity_events.get(event_type=ActivityEvent.EVENT_ACCEPTED)
        self.assertEqual(event.metadata.get("ip"), "203.0.113.42")

    def test_send_failure_does_not_persist_public_token(self):
        from unittest import mock
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("100.00"))
        self.client.login(username="owner", password="pass12345")
        with mock.patch("quotes.views.send_mail", side_effect=RuntimeError("SMTP down")):
            self.client.post(reverse("quotes:quote_send", args=[quote.pk]))
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_DRAFT)
        self.assertIsNone(quote.public_token)

    def test_line_item_reorder_updates_positions(self):
        quote = self.make_quote()
        a = QuoteLineItem.objects.create(quote=quote, description="A", quantity=1, unit_price=Decimal("10.00"), position=1)
        b = QuoteLineItem.objects.create(quote=quote, description="B", quantity=1, unit_price=Decimal("20.00"), position=2)
        self.client.login(username="owner", password="pass12345")
        self.client.post(reverse("quotes:line_item_reorder", args=[quote.pk]), {"item": [str(b.pk), str(a.pk)]})
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(b.position, 1)
        self.assertEqual(a.position, 2)

    def test_quote_duplicate_creates_new_number(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("100.00"))
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(reverse("quotes:quote_duplicate", args=[quote.pk]))
        self.assertEqual(response.status_code, 302)
        clones = Quote.objects.for_user(self.user).exclude(pk=quote.pk)
        self.assertEqual(clones.count(), 1)
        clone = clones.first()
        self.assertEqual(clone.line_items.count(), 1)
        self.assertNotEqual(clone.number, quote.number)

    def test_quote_delete_draft_removes_row(self):
        quote = self.make_quote()
        self.client.login(username="owner", password="pass12345")
        self.client.post(reverse("quotes:quote_delete", args=[quote.pk]))
        self.assertFalse(Quote.objects.filter(pk=quote.pk).exists())

    def test_quote_delete_non_draft_archives(self):
        quote = self.make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("100.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        self.client.login(username="owner", password="pass12345")
        self.client.post(reverse("quotes:quote_delete", args=[quote.pk]))
        quote.refresh_from_db()
        self.assertIsNotNone(quote.archived_at)

    def test_catalog_crud_round_trip(self):
        self.client.login(username="owner", password="pass12345")
        self.client.post(reverse("quotes:catalog_create"), {"name": "Logo Design", "description": "", "default_unit_price": "500.00", "unit": "each"})
        item = CatalogItem.objects.get(name="Logo Design")
        self.client.post(reverse("quotes:catalog_update", args=[item.pk]), {"name": "Logo Design", "description": "Refresh", "default_unit_price": "550.00", "unit": "each"})
        item.refresh_from_db()
        self.assertEqual(item.default_unit_price, Decimal("550.00"))
        self.client.post(reverse("quotes:catalog_delete", args=[item.pk]))
        self.assertFalse(CatalogItem.objects.filter(pk=item.pk).exists())

    def test_currency_template_tag(self):
        from quotes.templatetags.quote_extras import currency
        self.assertEqual(currency(Decimal("1234.5")), "$1,234.50")
        self.assertEqual(currency(None), "$0.00")
        self.assertEqual(currency(0), "$0.00")

    def test_status_badge_template_tag(self):
        from quotes.templatetags.quote_extras import status_badge
        self.assertIn("emerald", status_badge("accepted"))
        self.assertIn("slate", status_badge("anything-else"))

    def test_sort_link_toggles_direction(self):
        from django.template import Context, Template
        from django.test import RequestFactory
        request = RequestFactory().get("/", {"sort": "total", "dir": "desc"})
        template = Template("{% load quote_extras %}{% sort_link 'total' 'desc' %}")
        rendered = template.render(Context({"request": request}))
        self.assertIn("sort=total", rendered)
        self.assertIn("dir=asc", rendered)


class DeploymentConfigTests(TestCase):
    def test_requirements_declares_gunicorn(self):
        from pathlib import Path
        requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
        self.assertIn("gunicorn", requirements.lower())

    def test_railway_uses_production_settings(self):
        from pathlib import Path
        railway = (Path(__file__).resolve().parents[1] / "railway.toml").read_text()
        self.assertIn("config.settings.prod", railway)
        self.assertIn("gunicorn", railway)
