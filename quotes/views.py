import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    CatalogItemForm,
    ClientForm,
    CompanyProfileForm,
    QuoteCreateForm,
    QuoteForm,
    QuoteLineItemForm,
    SignupForm,
)
from .models import ActivityEvent, CatalogItem, Client, CompanyProfile, InvalidTransition, Quote, QuoteLineItem
from .pdf import render_quote_pdf


def is_hx(request):
    return request.headers.get("HX-Request") == "true"


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "") and not is_hx(request)


def add_toast(response, message, level="success"):
    response["HX-Trigger"] = json.dumps({"show-toast": {"message": message, "level": level}})
    return response


def forbidden_if_not_owner(obj, user):
    owner_id = obj.quote.owner_id if isinstance(obj, QuoteLineItem) else obj.owner_id
    if owner_id != user.id:
        raise PermissionDenied
    return obj


def get_owned(model, user, pk, **lookups):
    obj = get_object_or_404(model, pk=pk, **lookups)
    return forbidden_if_not_owner(obj, user)


def get_quote(user, pk):
    quote = get_object_or_404(
        Quote.objects.select_related("client", "owner").prefetch_related("line_items", "activity_events"),
        pk=pk,
    )
    forbidden_if_not_owner(quote, user)
    quote.check_expiry()
    quote.refresh_from_db()
    return quote


def favorite_count(user):
    return Quote.objects.for_user(user).filter(is_favorite=True, archived_at__isnull=True).count()


def profile_for(user):
    return CompanyProfile.objects.for_user(user).first()


def quote_queryset_from_request(request):
    quotes = Quote.objects.for_user(request.user).filter(archived_at__isnull=True).select_related("client")
    search = request.GET.get("q", "").strip()
    if search:
        quotes = quotes.filter(
            Q(number__icontains=search)
            | Q(client__name__icontains=search)
            | Q(client__company__icontains=search)
        )

    statuses = request.GET.getlist("status") or [s for s in request.GET.get("status", "").split(",") if s]
    if statuses:
        quotes = quotes.filter(status__in=statuses)

    client_id = request.GET.get("client")
    if client_id:
        quotes = quotes.filter(client_id=client_id)

    start = request.GET.get("start")
    end = request.GET.get("end")
    if start:
        quotes = quotes.filter(issue_date__gte=start)
    if end:
        quotes = quotes.filter(issue_date__lte=end)

    if request.GET.get("favorites") in {"1", "true", "on"}:
        quotes = quotes.filter(is_favorite=True)

    sort_map = {
        "number": "number",
        "client": "client__name",
        "issue_date": "issue_date",
        "total": "total",
        "status": "status",
    }
    sort = sort_map.get(request.GET.get("sort"), "issue_date")
    direction = "-" if request.GET.get("dir", "desc") == "desc" else ""
    return quotes.order_by(f"{direction}{sort}", "-id")


def quote_list_context(request):
    quotes = quote_queryset_from_request(request)
    paginator = Paginator(quotes, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return {
        "page_obj": page_obj,
        "quotes": page_obj.object_list,
        "total_count": paginator.count,
        "clients": Client.objects.for_user(request.user),
        "statuses": Quote.STATUS_CHOICES,
        "selected_statuses": request.GET.getlist("status") or [s for s in request.GET.get("status", "").split(",") if s],
        "favorite_count": favorite_count(request.user),
    }


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome. Your quote workspace is ready.")
            return redirect("quotes:dashboard")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def dashboard(request):
    events = ActivityEvent.objects.filter(quote__owner=request.user).select_related("quote", "quote__client")
    paginator = Paginator(events, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    if is_hx(request):
        return render(request, "quotes/partials/_activity_feed_items.html", {"page_obj": page_obj})

    quotes = Quote.objects.for_user(request.user).filter(archived_at__isnull=True)
    outstanding = quotes.filter(status__in=[Quote.STATUS_SENT, Quote.STATUS_VIEWED])
    accepted_month = quotes.filter(
        status=Quote.STATUS_ACCEPTED,
        accepted_at__year=timezone.now().year,
        accepted_at__month=timezone.now().month,
    )
    resolved = quotes.filter(status__in=[Quote.STATUS_ACCEPTED, Quote.STATUS_DECLINED, Quote.STATUS_EXPIRED])
    accepted_count = resolved.filter(status=Quote.STATUS_ACCEPTED).count()
    conversion_rate = int((accepted_count / resolved.count()) * 100) if resolved.count() else 0
    upcoming_expiries = outstanding.filter(expiry_date__lte=timezone.localdate() + timezone.timedelta(days=7))
    context = {
        "outstanding_count": outstanding.count(),
        "outstanding_value": sum((q.total for q in outstanding), Decimal("0.00")),
        "accepted_month_count": accepted_month.count(),
        "accepted_month_value": sum((q.total for q in accepted_month), Decimal("0.00")),
        "conversion_rate": conversion_rate,
        "page_obj": page_obj,
        "upcoming_expiries": upcoming_expiries,
    }
    return render(request, "quotes/dashboard.html", context)


@login_required
def profile_settings(request):
    profile = profile_for(request.user)
    if request.method == "POST":
        form = CompanyProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.owner = request.user
            saved.save()
            messages.success(request, "Company profile saved.")
            return redirect("quotes:profile_settings")
    else:
        form = CompanyProfileForm(instance=profile)
    return render(request, "quotes/profile_form.html", {"form": form})


@login_required
def quote_list(request):
    context = quote_list_context(request)
    if wants_json(request):
        return JsonResponse({"count": context["total_count"], "results": [quote.to_dict() for quote in context["quotes"]]})
    if is_hx(request):
        context["oob"] = True
        return render(request, "quotes/partials/_quote_feed.html", context)
    return render(request, "quotes/quote_list.html", context)


@login_required
def quote_create(request):
    if request.method == "POST":
        form = QuoteCreateForm(request.POST, owner=request.user)
        if form.is_valid():
            quote = form.save()
            messages.success(request, f"{quote.number} created.")
            return redirect("quotes:quote_detail", pk=quote.pk)
    else:
        form = QuoteCreateForm(owner=request.user)
    return render(request, "quotes/quote_create.html", {"form": form})


@login_required
def quote_detail(request, pk):
    quote = get_quote(request.user, pk)
    if wants_json(request):
        return JsonResponse(quote.to_dict())
    line_form = QuoteLineItemForm(owner=request.user, initial={"position": quote.line_items.count() + 1})
    form = QuoteForm(instance=quote, owner=request.user)
    context = {
        "quote": quote,
        "profile": profile_for(request.user),
        "form": form,
        "line_form": line_form,
        "favorite_count": favorite_count(request.user),
    }
    return render(request, "quotes/quote_detail.html", context)


@login_required
@require_POST
def quote_update(request, pk):
    quote = get_quote(request.user, pk)
    form = QuoteForm(request.POST, instance=quote, owner=request.user)
    if form.is_valid():
        quote = form.save()
        quote.record_event(ActivityEvent.EVENT_EDITED)
        response = render(
            request,
            "quotes/partials/_quote_header.html",
            {"quote": quote, "form": QuoteForm(instance=quote, owner=request.user)},
        )
        return add_toast(response, "Quote header saved.")
    response = render(request, "quotes/partials/_quote_header_form.html", {"quote": quote, "form": form}, status=422)
    return add_toast(response, "Please fix the quote header.", "error")


@login_required
@require_POST
def quote_delete(request, pk):
    quote = get_quote(request.user, pk)
    number = quote.number
    if quote.status == Quote.STATUS_DRAFT:
        quote.delete()
    else:
        quote.archived_at = timezone.now()
        quote.save(update_fields=["archived_at", "updated_at"])
    messages.success(request, f"{number} removed from the active quote list.")
    return redirect("quotes:quote_list")


@login_required
@require_POST
def quote_duplicate(request, pk):
    quote = get_quote(request.user, pk)
    clone = quote.duplicate_for_owner()
    messages.success(request, f"{quote.number} duplicated as {clone.number}.")
    return redirect("quotes:quote_detail", pk=clone.pk)


@login_required
@require_POST
def quote_send(request, pk):
    quote = get_quote(request.user, pk)
    try:
        quote.ensure_public_token()
        public_url = request.build_absolute_uri(quote.public_url)
        send_mail(
            subject=f"Quote {quote.number} from {profile_for(request.user) or request.user}",
            message=f"Hello {quote.client.name},\n\nYour quote is ready:\n{public_url}\n\nThank you.",
            from_email=None,
            recipient_list=[quote.client.email] if quote.client.email else [],
            fail_silently=False,
        )
        quote.transition_to(Quote.STATUS_SENT, ActivityEvent.EVENT_SENT, {"public_url": public_url})
        messages.success(request, f"{quote.number} sent.")
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    return redirect("quotes:quote_detail", pk=quote.pk)


@login_required
@require_POST
def quote_toggle_favorite(request, pk):
    quote = get_quote(request.user, pk)
    quote.is_favorite = not quote.is_favorite
    quote.save(update_fields=["is_favorite", "updated_at"])
    response = render(
        request,
        "quotes/partials/_quote_row_response.html",
        {"quote": quote, "favorite_count": favorite_count(request.user)},
    )
    return add_toast(response, "Favorite updated.", "info")


@login_required
def quote_pdf(request, pk):
    quote = get_quote(request.user, pk)
    profile = profile_for(request.user)
    buffer = render_quote_pdf(quote, profile)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{quote.number}.pdf"'
    return response


@login_required
@require_POST
def line_item_add(request, pk):
    quote = get_quote(request.user, pk)
    form = QuoteLineItemForm(request.POST, owner=request.user)
    if form.is_valid():
        item = form.save(commit=False)
        item.quote = quote
        if not item.position:
            item.position = quote.line_items.count() + 1
        item.save()
        quote.record_event(ActivityEvent.EVENT_EDITED, {"line_item": item.id, "action": "added"})
        response = render(
            request,
            "quotes/partials/_line_item_response.html",
            {"item": item, "quote": quote, "favorite_count": favorite_count(request.user)},
        )
        return add_toast(response, "Line item added.")
    return render(request, "quotes/partials/_line_item_form.html", {"form": form, "quote": quote}, status=422)


@login_required
@require_POST
def line_item_update(request, pk, item_pk):
    quote = get_quote(request.user, pk)
    item = get_owned(QuoteLineItem, request.user, item_pk, quote=quote)
    form = QuoteLineItemForm(request.POST, instance=item, owner=request.user)
    if form.is_valid():
        item = form.save()
        quote.record_event(ActivityEvent.EVENT_EDITED, {"line_item": item.id, "action": "edited"})
        quote.refresh_from_db()
        response = render(
            request,
            "quotes/partials/_line_item_response.html",
            {"item": item, "quote": quote, "favorite_count": favorite_count(request.user)},
        )
        return add_toast(response, "Line item updated.")
    return render(request, "quotes/partials/_line_item_row.html", {"item": item, "quote": quote, "form": form}, status=422)


@login_required
@require_POST
def line_item_delete(request, pk, item_pk):
    quote = get_quote(request.user, pk)
    item = get_owned(QuoteLineItem, request.user, item_pk, quote=quote)
    item.delete()
    quote.record_event(ActivityEvent.EVENT_EDITED, {"line_item": item_pk, "action": "deleted"})
    quote.refresh_from_db()
    response = render(
        request,
        "quotes/partials/_line_item_delete_response.html",
        {"quote": quote, "favorite_count": favorite_count(request.user)},
    )
    return add_toast(response, "Line item deleted.")


@login_required
@require_POST
def line_item_reorder(request, pk):
    quote = get_quote(request.user, pk)
    ids = request.POST.getlist("item")
    if not ids:
        return HttpResponseBadRequest("No item order supplied.")
    items = {str(item.id): item for item in quote.line_items.all()}
    for index, item_id in enumerate(ids, start=1):
        if item_id in items:
            QuoteLineItem.objects.filter(pk=item_id, quote=quote).update(position=index)
    quote.record_event(ActivityEvent.EVENT_EDITED, {"action": "reordered"})
    return add_toast(HttpResponse(""), "Line items reordered.", "info")


@login_required
def client_list(request):
    clients = Client.objects.for_user(request.user)
    search = request.GET.get("q", "").strip()
    if search:
        clients = clients.filter(Q(name__icontains=search) | Q(company__icontains=search) | Q(email__icontains=search))
    context = {"clients": clients, "form": ClientForm(owner=request.user)}
    if is_hx(request):
        return render(request, "quotes/partials/_client_table.html", context)
    return render(request, "quotes/client_list.html", context)


@login_required
def client_create(request):
    form = ClientForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        if is_hx(request):
            return add_toast(render(request, "quotes/partials/_client_row.html", {"client": client}), "Client created.")
        messages.success(request, "Client created.")
        return redirect("quotes:client_list")
    template = "quotes/partials/_client_form.html" if is_hx(request) else "quotes/client_form.html"
    return render(request, template, {"form": form})


@login_required
def client_update(request, pk):
    client = get_owned(Client, request.user, pk)
    form = ClientForm(request.POST or None, instance=client, owner=request.user)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        if is_hx(request):
            return add_toast(render(request, "quotes/partials/_client_row.html", {"client": client}), "Client saved.")
        messages.success(request, "Client saved.")
        return redirect("quotes:client_list")
    template = "quotes/partials/_client_form.html" if is_hx(request) else "quotes/client_form.html"
    return render(request, template, {"form": form, "client": client})


@login_required
@require_POST
def client_delete(request, pk):
    client = get_owned(Client, request.user, pk)
    client.delete()
    if is_hx(request):
        return add_toast(HttpResponse(""), "Client deleted.")
    messages.success(request, "Client deleted.")
    return redirect("quotes:client_list")


@login_required
def catalog_list(request):
    items = CatalogItem.objects.for_user(request.user)
    search = request.GET.get("q", "").strip()
    if search:
        items = items.filter(Q(name__icontains=search) | Q(description__icontains=search))
    quotes = Quote.objects.for_user(request.user).filter(status=Quote.STATUS_DRAFT, archived_at__isnull=True)
    context = {"items": items, "form": CatalogItemForm(owner=request.user), "draft_quotes": quotes}
    if is_hx(request):
        return render(request, "quotes/partials/_catalog_table.html", context)
    return render(request, "quotes/catalog_list.html", context)


@login_required
def catalog_create(request):
    form = CatalogItemForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        if is_hx(request):
            return add_toast(render(request, "quotes/partials/_catalog_row.html", {"item": item}), "Catalog item created.")
        messages.success(request, "Catalog item created.")
        return redirect("quotes:catalog_list")
    template = "quotes/partials/_catalog_form.html" if is_hx(request) else "quotes/catalog_form.html"
    return render(request, template, {"form": form})


@login_required
def catalog_update(request, pk):
    item = get_owned(CatalogItem, request.user, pk)
    form = CatalogItemForm(request.POST or None, instance=item, owner=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        if is_hx(request):
            return add_toast(render(request, "quotes/partials/_catalog_row.html", {"item": item}), "Catalog item saved.")
        messages.success(request, "Catalog item saved.")
        return redirect("quotes:catalog_list")
    template = "quotes/partials/_catalog_form.html" if is_hx(request) else "quotes/catalog_form.html"
    return render(request, template, {"form": form, "item": item})


@login_required
@require_POST
def catalog_delete(request, pk):
    item = get_owned(CatalogItem, request.user, pk)
    item.delete()
    if is_hx(request):
        return add_toast(HttpResponse(""), "Catalog item deleted.")
    messages.success(request, "Catalog item deleted.")
    return redirect("quotes:catalog_list")


@login_required
@require_POST
def catalog_add_to_quote(request, pk):
    item = get_owned(CatalogItem, request.user, pk)
    quote = get_quote(request.user, request.POST.get("quote"))
    line_item = QuoteLineItem.objects.create(
        quote=quote,
        catalog_item=item,
        description=item.description or item.name,
        quantity=1,
        unit_price=item.default_unit_price,
        position=quote.line_items.count() + 1,
    )
    quote.record_event(ActivityEvent.EVENT_EDITED, {"line_item": line_item.id, "source": "catalog"})
    messages.success(request, f"{item.name} added to {quote.number}.")
    return redirect("quotes:quote_detail", pk=quote.pk)


def public_quote(request, token):
    quote = get_object_or_404(Quote.objects.select_related("client", "owner").prefetch_related("line_items"), public_token=token)
    quote.check_expiry()
    quote.refresh_from_db()
    if request.method == "POST":
        action = request.POST.get("action")
        if action not in {"accept", "decline"}:
            return HttpResponseBadRequest("Unknown action.")
        status = Quote.STATUS_ACCEPTED if action == "accept" else Quote.STATUS_DECLINED
        event = ActivityEvent.EVENT_ACCEPTED if action == "accept" else ActivityEvent.EVENT_DECLINED
        try:
            quote.transition_to(
                status,
                event,
                {
                    "ip": request.META.get("REMOTE_ADDR", ""),
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                },
            )
        except InvalidTransition:
            pass
        quote.refresh_from_db()
        if is_hx(request):
            return render(request, "quotes/partials/_public_thank_you.html", {"quote": quote})
    elif quote.status == Quote.STATUS_SENT:
        quote.transition_to(
            Quote.STATUS_VIEWED,
            ActivityEvent.EVENT_VIEWED,
            {"ip": request.META.get("REMOTE_ADDR", ""), "user_agent": request.META.get("HTTP_USER_AGENT", "")},
        )
        quote.refresh_from_db()
    return render(request, "quotes/public_quote.html", {"quote": quote, "profile": profile_for(quote.owner)})


def public_quote_pdf(request, token):
    quote = get_object_or_404(Quote.objects.select_related("client", "owner").prefetch_related("line_items"), public_token=token)
    buffer = render_quote_pdf(quote, profile_for(quote.owner))
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{quote.number}.pdf"'
    return response
