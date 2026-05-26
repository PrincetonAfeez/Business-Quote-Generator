""" Test views extra for the quotes app """

from decimal import Decimal
from unittest import mock

import pytest
from django.urls import reverse
from django.utils import timezone

from quotes.models import ActivityEvent, CatalogItem, Client, Quote, QuoteLineItem
from quotes.views import SEND_MARKED_SENT_FAILURE


@pytest.mark.django_db
class TestAuthAndNavigation:
    def test_login_page_renders(self, client):
        response = client.get(reverse("login"))
        assert response.status_code == 200

    def test_logout_requires_post(self, auth_client):
        response = auth_client.get(reverse("logout"))
        assert response.status_code in {405, 302}

    def test_client_list_requires_login(self, client):
        assert client.get(reverse("quotes:client_list")).status_code == 302

    def test_catalog_list_requires_login(self, client):
        assert client.get(reverse("quotes:catalog_list")).status_code == 302


@pytest.mark.django_db
class TestClientViews:
    def test_client_list_renders(self, auth_client, client_record):
        response = auth_client.get(reverse("quotes:client_list"))
        assert response.status_code == 200
        assert client_record.name.encode() in response.content

    def test_client_list_hx_returns_table_partial(self, auth_client, client_record):
        response = auth_client.get(reverse("quotes:client_list"), HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"<thead" in response.content

    def test_client_row_partial(self, auth_client, client_record):
        response = auth_client.get(reverse("quotes:client_row", args=[client_record.pk]), HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert f'id="client-{client_record.pk}"'.encode() in response.content

    def test_client_create_get_redirects_to_list(self, auth_client):
        response = auth_client.get(reverse("quotes:client_create"))
        assert response.status_code == 302

    def test_client_create_hx_validation_error_retargets(self, auth_client):
        response = auth_client.post(
            reverse("quotes:client_create"),
            {"name": "", "company": "", "email": "", "phone": "", "billing_address": "", "notes": ""},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 422
        assert response.headers.get("HX-Retarget") == "#client-create"

    def test_client_delete_hx_success(self, auth_client, user):
        orphan = Client.objects.create(owner=user, name="Delete Me")
        response = auth_client.post(reverse("quotes:client_delete", args=[orphan.pk]), HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert not Client.objects.filter(pk=orphan.pk).exists()

    def test_client_update_cross_user_forbidden(self, client, user, other_client):
        client.login(username="owner", password="pass12345")
        response = client.get(reverse("quotes:client_update", args=[other_client.pk]), HTTP_HX_REQUEST="true")
        assert response.status_code == 403


@pytest.mark.django_db
class TestCatalogViews:
    def test_catalog_list_renders(self, auth_client, user):
        CatalogItem.objects.create(owner=user, name="SKU", default_unit_price=Decimal("10.00"))
        response = auth_client.get(reverse("quotes:catalog_list"))
        assert response.status_code == 200
        assert b"SKU" in response.content

    def test_catalog_list_hx_returns_table(self, auth_client, user):
        CatalogItem.objects.create(owner=user, name="SKU", default_unit_price=Decimal("10.00"))
        response = auth_client.get(reverse("quotes:catalog_list"), HTTP_HX_REQUEST="true")
        assert b"<thead" in response.content

    def test_catalog_row_partial(self, auth_client, user):
        item = CatalogItem.objects.create(owner=user, name="SKU", default_unit_price=Decimal("10.00"))
        response = auth_client.get(reverse("quotes:catalog_row", args=[item.pk]), HTTP_HX_REQUEST="true")
        assert f'id="catalog-{item.pk}"'.encode() in response.content

    def test_catalog_add_to_quote_success(self, auth_client, user, make_quote):
        quote = make_quote()
        item = CatalogItem.objects.create(owner=user, name="SKU", default_unit_price=Decimal("75.00"))
        response = auth_client.post(reverse("quotes:catalog_add_to_quote", args=[item.pk]), {"quote": str(quote.pk)})
        assert response.status_code == 302
        assert quote.line_items.filter(catalog_item=item).exists()

    def test_catalog_add_to_quote_invalid_quote_id(self, auth_client, user):
        item = CatalogItem.objects.create(owner=user, name="SKU", default_unit_price=Decimal("10.00"))
        response = auth_client.post(reverse("quotes:catalog_add_to_quote", args=[item.pk]), {"quote": "not-a-number"})
        assert response.status_code == 302

    def test_catalog_create_hx_validation_error(self, auth_client):
        response = auth_client.post(
            reverse("quotes:catalog_create"),
            {"name": "", "description": "", "default_unit_price": "-1", "unit": "each"},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 422

    def test_catalog_delete_hx(self, auth_client, user):
        item = CatalogItem.objects.create(owner=user, name="Remove", default_unit_price=Decimal("1.00"))
        response = auth_client.post(reverse("quotes:catalog_delete", args=[item.pk]), HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert not CatalogItem.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
class TestQuoteViewsExtra:
    def test_quote_create_post(self, auth_client, client_record):
        response = auth_client.post(reverse("quotes:quote_create"), {"client": client_record.pk})
        assert response.status_code == 302
        assert Quote.objects.filter(client=client_record).exists()

    def test_quote_detail_json(self, auth_client, make_quote):
        quote = make_quote()
        response = auth_client.get(reverse("quotes:quote_detail", args=[quote.pk]), HTTP_ACCEPT="application/json")
        assert response.status_code == 200
        assert response.json()["id"] == quote.pk

    def test_quote_update_locked_returns_409_hx(self, auth_client, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        response = auth_client.post(
            reverse("quotes:quote_update", args=[quote.pk]),
            {
                "client": quote.client_id,
                "issue_date": quote.issue_date.isoformat(),
                "expiry_date": quote.expiry_date.isoformat(),
                "tax_rate": "0.00",
                "discount_type": Quote.DISCOUNT_NONE,
                "discount_value": "0.00",
                "notes": "Nope",
                "terms": "",
                "is_favorite": "",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 409

    def test_quote_revoke_without_token_shows_info(self, auth_client, make_quote):
        quote = make_quote()
        response = auth_client.post(reverse("quotes:quote_revoke_public_link", args=[quote.pk]), follow=True)
        assert response.status_code == 200
        assert b"no public link" in response.content.lower()

    def test_line_item_update_hx(self, auth_client, make_quote):
        quote = make_quote()
        item = QuoteLineItem.objects.create(quote=quote, description="Old", quantity=1, unit_price=Decimal("10.00"))
        response = auth_client.post(
            reverse("quotes:line_item_update", args=[quote.pk, item.pk]),
            {
                "description": "New",
                "quantity": "2",
                "unit_price": "10.00",
                "position": "1",
                "catalog_item": "",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.description == "New"
        assert item.quantity == Decimal("2.00")

    def test_line_item_reorder_empty_list_bad_request(self, auth_client, make_quote):
        quote = make_quote()
        response = auth_client.post(reverse("quotes:line_item_reorder", args=[quote.pk]), {})
        assert response.status_code == 400

    def test_line_item_reorder_invalid_id_bad_request(self, auth_client, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="A", quantity=1, unit_price=Decimal("10.00"))
        response = auth_client.post(reverse("quotes:line_item_reorder", args=[quote.pk]), {"item": ["99999"]})
        assert response.status_code == 400

    def test_line_item_reorder_locked_quote_conflict(self, auth_client, make_quote):
        quote = make_quote()
        item = QuoteLineItem.objects.create(quote=quote, description="A", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        response = auth_client.post(
            reverse("quotes:line_item_reorder", args=[quote.pk]),
            {"item": [str(item.pk)]},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 409

    def test_send_failure_message_is_generic(self, auth_client, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("100.00"))
        with mock.patch("quotes.views.send_mail", side_effect=RuntimeError("SMTP down")):
            response = auth_client.post(reverse("quotes:quote_send", args=[quote.pk]), follow=True)
        assert b"SMTP" not in response.content
        assert SEND_MARKED_SENT_FAILURE.format(number=quote.number).encode() in response.content

    def test_quote_toggle_favorite_non_hx_redirects(self, auth_client, make_quote):
        quote = make_quote()
        response = auth_client.post(reverse("quotes:quote_toggle_favorite", args=[quote.pk]))
        assert response.status_code == 302
        quote.refresh_from_db()
        assert quote.is_favorite is True


@pytest.mark.django_db
class TestPublicViewsExtra:
    def test_public_quote_invalid_token_404(self, client):
        assert client.get(reverse("quotes:public_quote", args=["invalid-token-not-found-xxxxxxxxxxxx"])).status_code == 404

    def test_public_accept_from_sent_skips_viewed(self, client, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        response = client.post(
            reverse("quotes:public_quote", args=[quote.public_token]),
            {"action": "accept"},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        quote.refresh_from_db()
        assert quote.status == Quote.STATUS_ACCEPTED

    def test_public_quote_pdf_smoke(self, client, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        response = client.get(reverse("quotes:public_quote_pdf", args=[quote.public_token]))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_public_post_invalid_action(self, client, make_quote):
        quote = make_quote()
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        response = client.post(reverse("quotes:public_quote", args=[quote.public_token]), {"action": "noop"})
        assert response.status_code in {200, 302, 400}

    def test_public_get_expires_stale_quote(self, client, make_quote):
        quote = make_quote(issue_date=timezone.localdate() - timezone.timedelta(days=30))
        Quote.objects.filter(pk=quote.pk).update(expiry_date=timezone.localdate() - timezone.timedelta(days=1))
        quote.refresh_from_db()
        QuoteLineItem.objects.create(quote=quote, description="W", quantity=1, unit_price=Decimal("10.00"))
        quote.ensure_public_token()
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT)
        client.get(reverse("quotes:public_quote", args=[quote.public_token]))
        quote.refresh_from_db()
        assert quote.status == Quote.STATUS_EXPIRED


@pytest.mark.django_db
class TestSignupValidation:
    def test_signup_invalid_password_mismatch(self, client):
        response = client.post(
            reverse("quotes:signup"),
            {
                "username": "bad",
                "email": "",
                "password1": "complex-pass-12345",
                "password2": "different-pass-12345",
            },
        )
        assert response.status_code == 200
        assert b"password" in response.content.lower()
