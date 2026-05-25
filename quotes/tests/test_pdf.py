from decimal import Decimal

import pytest

from quotes.models import QuoteLineItem
from quotes.pdf import _safe, _safe_multiline, render_quote_pdf


class TestPdfHelpers:
    def test_safe_escapes_html(self):
        assert "&lt;script&gt;" in _safe("<script>")

    def test_safe_multiline_replaces_newlines(self):
        assert _safe_multiline("a\nb") == "a<br/>b"

    def test_safe_handles_none(self):
        assert _safe(None) == ""


class TestRenderQuotePdf:
    def test_returns_pdf_bytes(self, make_quote, company_profile):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Build", quantity=1, unit_price=Decimal("100.00"))
        quote.refresh_from_db()
        buffer = render_quote_pdf(quote, company_profile)
        data = buffer.getvalue()
        assert data.startswith(b"%PDF")

    def test_includes_terms_and_notes(self, make_quote, company_profile):
        quote = make_quote(notes="Internal note", terms="Net 30")
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("50.00"))
        quote.refresh_from_db()
        pdf = render_quote_pdf(quote, company_profile).getvalue()
        assert len(pdf) > 1000

    def test_public_pdf_can_omit_client_email(self, make_quote, company_profile):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("10.00"))
        quote.refresh_from_db()
        buffer = render_quote_pdf(quote, company_profile, include_client_email=False)
        assert buffer.getvalue().startswith(b"%PDF")

    def test_works_without_profile(self, make_quote):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="Work", quantity=1, unit_price=Decimal("10.00"))
        quote.refresh_from_db()
        assert render_quote_pdf(quote, None).getvalue().startswith(b"%PDF")

    def test_escapes_markup_in_description(self, make_quote, company_profile):
        quote = make_quote()
        QuoteLineItem.objects.create(quote=quote, description="<b>Inject</b>", quantity=1, unit_price=Decimal("1.00"))
        quote.refresh_from_db()
        assert render_quote_pdf(quote, company_profile).getvalue().startswith(b"%PDF")
