from django import template

from quotes.models import money


register = template.Library()


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.filter
def currency(value):
    return f"${money(value):,.2f}"


@register.filter
def status_badge(status):
    return {
        "draft": "bg-slate-100 text-slate-700",
        "sent": "bg-sky-100 text-sky-700",
        "viewed": "bg-cyan-100 text-cyan-700",
        "accepted": "bg-emerald-100 text-emerald-700",
        "declined": "bg-rose-100 text-rose-700",
        "expired": "bg-amber-100 text-amber-700",
    }.get(status, "bg-slate-100 text-slate-700")
