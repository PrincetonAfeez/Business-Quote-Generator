""" Test fixtures for the quotes app """

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from quotes.models import ActivityEvent, Client, CompanyProfile, Quote


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def user(db):
    return User.objects.create_user("owner", password="pass12345")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("other", password="pass12345")


@pytest.fixture
def client_record(db, user):
    return Client.objects.create(
        owner=user,
        name="Ada Lovelace",
        company="Analytical Works",
        email="ada@example.com",
    )


@pytest.fixture
def other_client(db, other_user):
    return Client.objects.create(owner=other_user, name="Grace Hopper")


@pytest.fixture
def company_profile(db, user):
    return CompanyProfile.objects.create(
        owner=user,
        business_name="Northstar Studio",
        default_tax_rate=Decimal("8.25"),
        default_terms="Due on receipt",
    )


@pytest.fixture
def make_quote(db, user, client_record):
    def _make_quote(**kwargs):
        today = timezone.localdate()
        defaults = {
            "owner": user,
            "client": client_record,
            "issue_date": today,
            "tax_rate": Decimal("0.00"),
        }
        defaults.update(kwargs)
        if "expiry_date" not in defaults:
            defaults["expiry_date"] = defaults["issue_date"] + timedelta(days=30)
        quote = Quote.objects.create(**defaults)
        quote.record_event(ActivityEvent.EVENT_CREATED)
        return quote

    return _make_quote


@pytest.fixture
def auth_client(client, user):
    client.login(username="owner", password="pass12345")
    return client


@pytest.fixture
def project_root():
    return PROJECT_ROOT
