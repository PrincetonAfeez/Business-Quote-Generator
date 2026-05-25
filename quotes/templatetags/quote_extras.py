from django import template

from quotes.models import Quote, money


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


@register.simple_tag(takes_context=True)
def sort_link(context, column, default_dir="asc"):
    """Toggle direction for the given column, or set it as the new sort key."""
    request = context["request"]
    current_sort = request.GET.get("sort", "issue_date")
    current_dir = request.GET.get("dir", "desc")
    if current_sort == column:
        new_dir = "asc" if current_dir == "desc" else "desc"
    else:
        new_dir = default_dir
    query = request.GET.copy()
    query["sort"] = column
    query["dir"] = new_dir
    query.pop("page", None)
    return query.urlencode()


@register.simple_tag(takes_context=True)
def sort_indicator(context, column):
    request = context["request"]
    if request.GET.get("sort", "issue_date") != column:
        return ""
    return "↑" if request.GET.get("dir", "desc") == "asc" else "↓"


@register.filter
def currency(value):
    return f"${money(value):,.2f}"


@register.filter
def quote_has_status(quote, names):
    allowed = {
        value
        for name in names.split(",")
        if (value := getattr(Quote, f"STATUS_{name.strip().upper()}", None)) is not None
    }
    return quote.status in allowed


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
