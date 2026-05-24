from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string


MONEY_PLACES = Decimal("0.01")


def money(value):
    return Decimal(value or 0).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


class InvalidTransition(ValueError):
    pass


class OwnedQuerySet(models.QuerySet):
    def for_user(self, user):
        if not user or not user.is_authenticated:
            return self.none()
        return self.filter(owner=user)


class OwnedManager(models.Manager.from_queryset(OwnedQuerySet)):
    pass


class CompanyProfile(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_profile")
    business_name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=80, blank=True)
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    default_terms = models.TextField(blank=True)
    default_validity_days = models.PositiveIntegerField(default=30)

    objects = OwnedManager()

    def __str__(self):
        return self.business_name


class Client(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    billing_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OwnedManager()

    class Meta:
        ordering = ["name", "company"]

    def __str__(self):
        return self.company or self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "company": self.company,
            "email": self.email,
            "phone": self.phone,
            "billing_address": self.billing_address,
            "notes": self.notes,
        }


class CatalogItem(models.Model):
    UNIT_HOUR = "hour"
    UNIT_DAY = "day"
    UNIT_EACH = "each"
    UNIT_SQFT = "sqft"
    UNIT_WORD = "word"
    UNIT_PAGE = "page"
    UNIT_CHOICES = [
        (UNIT_HOUR, "Hour"),
        (UNIT_DAY, "Day"),
        (UNIT_EACH, "Each"),
        (UNIT_SQFT, "Sqft"),
        (UNIT_WORD, "Word"),
        (UNIT_PAGE, "Page"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="catalog_items")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    default_unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default=UNIT_EACH)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OwnedManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "default_unit_price": str(money(self.default_unit_price)),
            "unit": self.unit,
        }


class QuoteCounter(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quote_counters")
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "year"], name="unique_quote_counter_per_user_year")
        ]

    def __str__(self):
        return f"{self.owner} {self.year}: {self.last_number}"


class Quote(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_VIEWED = "viewed"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_VIEWED, "Viewed"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_EXPIRED, "Expired"),
    ]
    FINAL_STATUSES = {STATUS_ACCEPTED, STATUS_DECLINED, STATUS_EXPIRED}

    DISCOUNT_NONE = "none"
    DISCOUNT_PERCENT = "percent"
    DISCOUNT_FLAT = "flat"
    DISCOUNT_CHOICES = [
        (DISCOUNT_NONE, "None"),
        (DISCOUNT_PERCENT, "Percent"),
        (DISCOUNT_FLAT, "Flat"),
    ]

    TRANSITIONS = {
        STATUS_DRAFT: {STATUS_SENT, STATUS_EXPIRED},
        STATUS_SENT: {STATUS_VIEWED, STATUS_ACCEPTED, STATUS_DECLINED, STATUS_EXPIRED},
        STATUS_VIEWED: {STATUS_ACCEPTED, STATUS_DECLINED, STATUS_EXPIRED},
        STATUS_ACCEPTED: set(),
        STATUS_DECLINED: set(),
        STATUS_EXPIRED: set(),
    }

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quotes")
    number = models.CharField(max_length=20, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="quotes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    issue_date = models.DateField(default=timezone.localdate)
    expiry_date = models.DateField()
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_CHOICES, default=DISCOUNT_NONE)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    public_token = models.CharField(max_length=32, unique=True, blank=True, null=True, editable=False)
    viewed_at = models.DateTimeField(blank=True, null=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    declined_at = models.DateTimeField(blank=True, null=True)
    is_favorite = models.BooleanField(default=False)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OwnedManager()

    class Meta:
        ordering = ["-issue_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "number"], name="unique_quote_number_per_user")
        ]

    def __str__(self):
        return self.number or "Unsaved quote"

    def get_absolute_url(self):
        return reverse("quotes:quote_detail", args=[self.pk])

    @property
    def public_url(self):
        if not self.public_token:
            return ""
        return reverse("quotes:public_quote", args=[self.public_token])

    def clean(self):
        if self.discount_value < 0:
            raise ValidationError({"discount_value": "Discount cannot be negative."})
        if self.discount_type == self.DISCOUNT_PERCENT and self.discount_value > 100:
            raise ValidationError({"discount_value": "Percent discount cannot exceed 100."})

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._next_number()
        super().save(*args, **kwargs)

    def _next_number(self):
        if not self.owner_id:
            raise ValueError("Quote owner is required before numbering.")
        year = (self.issue_date or timezone.localdate()).year
        with transaction.atomic():
            counter, _ = QuoteCounter.objects.select_for_update().get_or_create(
                owner=self.owner,
                year=year,
                defaults={"last_number": 0},
            )
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
        return f"Q-{year}-{counter.last_number:04d}"

    def ensure_public_token(self):
        if self.public_token:
            return self.public_token
        while True:
            token = get_random_string(32)
            if not Quote.objects.filter(public_token=token).exists():
                self.public_token = token
                self.save(update_fields=["public_token", "updated_at"])
                return token

    def calculate_totals(self, save=False):
        subtotal = Decimal("0.00")
        if self.pk:
            subtotal = sum((item.line_total for item in self.line_items.all()), Decimal("0.00"))
        subtotal = money(subtotal)

        if self.discount_value < 0:
            raise ValueError("Discount cannot be negative.")
        if self.discount_type == self.DISCOUNT_PERCENT:
            if self.discount_value > 100:
                raise ValueError("Percent discount cannot exceed 100.")
            discount = subtotal * Decimal(self.discount_value) / Decimal("100")
        elif self.discount_type == self.DISCOUNT_FLAT:
            discount = Decimal(self.discount_value)
        else:
            discount = Decimal("0.00")

        discount = min(money(discount), subtotal)
        taxable_subtotal = subtotal - discount
        tax = money(taxable_subtotal * Decimal(self.tax_rate) / Decimal("100"))
        total = money(taxable_subtotal + tax)

        self.subtotal = subtotal
        self.discount_amount = discount
        self.tax_amount = tax
        self.total = total
        if save:
            self.save(update_fields=["subtotal", "discount_amount", "tax_amount", "total", "updated_at"])
        return self

    def transition_to(self, new_status, event_type=None, metadata=None):
        if new_status == self.status:
            return
        allowed = self.TRANSITIONS[self.status]
        if new_status not in allowed:
            raise InvalidTransition(f"Cannot transition quote {self.number} from {self.status} to {new_status}.")

        now = timezone.now()
        self.status = new_status
        update_fields = ["status", "updated_at"]
        if new_status == self.STATUS_VIEWED and not self.viewed_at:
            self.viewed_at = now
            update_fields.append("viewed_at")
        elif new_status == self.STATUS_ACCEPTED:
            self.accepted_at = now
            update_fields.append("accepted_at")
        elif new_status == self.STATUS_DECLINED:
            self.declined_at = now
            update_fields.append("declined_at")
        self.save(update_fields=update_fields)
        self.record_event(event_type or new_status, metadata=metadata)

    def check_expiry(self):
        if self.status not in self.FINAL_STATUSES and self.expiry_date < timezone.localdate():
            self.transition_to(self.STATUS_EXPIRED, ActivityEvent.EVENT_EXPIRED)
        return self.status

    def record_event(self, event_type, metadata=None):
        ActivityEvent.objects.create(quote=self, event_type=event_type, metadata=metadata or {})

    def duplicate_for_owner(self):
        clone = Quote.objects.create(
            owner=self.owner,
            client=self.client,
            issue_date=timezone.localdate(),
            expiry_date=self.expiry_date,
            tax_rate=self.tax_rate,
            discount_type=self.discount_type,
            discount_value=self.discount_value,
            notes=self.notes,
            terms=self.terms,
        )
        for item in self.line_items.order_by("position", "id"):
            QuoteLineItem.objects.create(
                quote=clone,
                catalog_item=item.catalog_item,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                position=item.position,
            )
        clone.calculate_totals(save=True)
        clone.record_event(ActivityEvent.EVENT_DUPLICATED, {"source_quote": self.number})
        return clone

    def to_dict(self):
        return {
            "id": self.id,
            "number": self.number,
            "client": self.client.to_dict(),
            "status": self.status,
            "issue_date": self.issue_date.isoformat(),
            "expiry_date": self.expiry_date.isoformat(),
            "tax_rate": str(self.tax_rate),
            "discount_type": self.discount_type,
            "discount_value": str(self.discount_value),
            "subtotal": str(self.subtotal),
            "discount_amount": str(self.discount_amount),
            "tax_amount": str(self.tax_amount),
            "total": str(self.total),
            "notes": self.notes,
            "terms": self.terms,
            "is_favorite": self.is_favorite,
            "line_items": [item.to_dict() for item in self.line_items.order_by("position", "id")],
        }


class QuoteLineItem(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="line_items")
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.SET_NULL, blank=True, null=True)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), editable=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.description[:80]

    def save(self, *args, **kwargs):
        self.line_total = money(Decimal(self.quantity) * Decimal(self.unit_price))
        super().save(*args, **kwargs)
        self.quote.calculate_totals(save=True)

    def delete(self, *args, **kwargs):
        quote = self.quote
        result = super().delete(*args, **kwargs)
        quote.calculate_totals(save=True)
        return result

    def to_dict(self):
        return {
            "id": self.id,
            "catalog_item_id": self.catalog_item_id,
            "description": self.description,
            "quantity": str(self.quantity),
            "unit_price": str(self.unit_price),
            "line_total": str(self.line_total),
            "position": self.position,
        }


class ActivityEvent(models.Model):
    EVENT_CREATED = "created"
    EVENT_SENT = "sent"
    EVENT_VIEWED = "viewed"
    EVENT_ACCEPTED = "accepted"
    EVENT_DECLINED = "declined"
    EVENT_DUPLICATED = "duplicated"
    EVENT_EDITED = "edited"
    EVENT_EXPIRED = "expired"
    EVENT_CHOICES = [
        (EVENT_CREATED, "Created"),
        (EVENT_SENT, "Sent"),
        (EVENT_VIEWED, "Viewed"),
        (EVENT_ACCEPTED, "Accepted"),
        (EVENT_DECLINED, "Declined"),
        (EVENT_DUPLICATED, "Duplicated"),
        (EVENT_EDITED, "Edited"),
        (EVENT_EXPIRED, "Expired"),
    ]

    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="activity_events")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp", "-id"]

    def __str__(self):
        return f"{self.quote.number} {self.event_type}"
