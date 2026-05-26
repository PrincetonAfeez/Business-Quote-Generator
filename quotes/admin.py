""" Admin for the quotes app """

from django.contrib import admin

from .models import ActivityEvent, CatalogItem, Client, CompanyProfile, Quote, QuoteCounter, QuoteLineItem


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("business_name", "owner", "default_tax_rate", "default_validity_days")
    search_fields = ("business_name", "owner__username", "tax_id")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "email", "owner", "updated_at")
    search_fields = ("name", "company", "email", "owner__username")
    list_filter = ("created_at",)


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "default_unit_price", "owner", "updated_at")
    search_fields = ("name", "description", "owner__username")
    list_filter = ("unit",)


class QuoteLineItemInline(admin.TabularInline):
    model = QuoteLineItem
    extra = 0
    fields = ("description", "quantity", "unit_price", "line_total", "position")
    readonly_fields = ("line_total",)

    def _quote_locked(self, obj):
        return obj is not None and obj.status != Quote.STATUS_DRAFT

    def get_readonly_fields(self, request, obj=None):
        if self._quote_locked(obj):
            return self.fields
        return self.readonly_fields

    def has_add_permission(self, request, obj=None):
        if self._quote_locked(obj):
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if self._quote_locked(obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._quote_locked(obj):
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "status", "issue_date", "expiry_date", "total", "owner", "is_favorite")
    search_fields = ("number", "client__name", "client__company", "owner__username")
    list_filter = ("status", "is_favorite", "issue_date")
    readonly_fields = (
        "number",
        "status",
        "public_token",
        "viewed_at",
        "accepted_at",
        "declined_at",
        "subtotal",
        "tax_amount",
        "discount_amount",
        "total",
    )
    inlines = [QuoteLineItemInline]

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.status != Quote.STATUS_DRAFT:
            readonly += [
                "client",
                "issue_date",
                "expiry_date",
                "tax_rate",
                "discount_type",
                "discount_value",
                "notes",
                "terms",
                "is_favorite",
                "archived_at",
            ]
        return readonly


@admin.register(QuoteLineItem)
class QuoteLineItemAdmin(admin.ModelAdmin):
    list_display = ("quote", "description", "quantity", "unit_price", "line_total", "position")
    search_fields = ("quote__number", "description")
    readonly_fields = ("line_total",)

    def has_change_permission(self, request, obj=None):
        if obj and obj.quote.status != Quote.STATUS_DRAFT:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.quote.status != Quote.STATUS_DRAFT:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ("quote", "event_type", "timestamp")
    search_fields = ("quote__number",)
    list_filter = ("event_type", "timestamp")
    list_select_related = ("quote",)


@admin.register(QuoteCounter)
class QuoteCounterAdmin(admin.ModelAdmin):
    list_display = ("owner", "year", "last_number")
    list_filter = ("year",)
