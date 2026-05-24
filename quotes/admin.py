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


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "status", "issue_date", "expiry_date", "total", "owner", "is_favorite")
    search_fields = ("number", "client__name", "client__company", "owner__username")
    list_filter = ("status", "is_favorite", "issue_date")
    readonly_fields = ("number", "public_token", "viewed_at", "accepted_at", "declined_at")
    inlines = [QuoteLineItemInline]


@admin.register(QuoteLineItem)
class QuoteLineItemAdmin(admin.ModelAdmin):
    list_display = ("quote", "description", "quantity", "unit_price", "line_total", "position")
    search_fields = ("quote__number", "description")


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
