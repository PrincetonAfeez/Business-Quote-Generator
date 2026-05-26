""" URLs for the quotes app """

from django.urls import path

from . import views


app_name = "quotes"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("signup/", views.signup, name="signup"),
    path("profile/", views.profile_settings, name="profile_settings"),
    path("quotes/", views.quote_list, name="quote_list"),
    path("quotes/new/", views.quote_create, name="quote_create"),
    path("quotes/<int:pk>/", views.quote_detail, name="quote_detail"),
    path("quotes/<int:pk>/update/", views.quote_update, name="quote_update"),
    path("quotes/<int:pk>/delete/", views.quote_delete, name="quote_delete"),
    path("quotes/<int:pk>/duplicate/", views.quote_duplicate, name="quote_duplicate"),
    path("quotes/<int:pk>/send/", views.quote_send, name="quote_send"),
    path("quotes/<int:pk>/revoke-link/", views.quote_revoke_public_link, name="quote_revoke_public_link"),
    path("quotes/<int:pk>/favorite/", views.quote_toggle_favorite, name="quote_toggle_favorite"),
    path("quotes/<int:pk>/pdf/", views.quote_pdf, name="quote_pdf"),
    path("quotes/<int:pk>/lines/add/", views.line_item_add, name="line_item_add"),
    path("quotes/<int:pk>/lines/reorder/", views.line_item_reorder, name="line_item_reorder"),
    path("quotes/<int:pk>/lines/<int:item_pk>/update/", views.line_item_update, name="line_item_update"),
    path("quotes/<int:pk>/lines/<int:item_pk>/delete/", views.line_item_delete, name="line_item_delete"),
    path("clients/", views.client_list, name="client_list"),
    path("clients/new/", views.client_create, name="client_create"),
    path("clients/<int:pk>/edit/", views.client_update, name="client_update"),
    path("clients/<int:pk>/row/", views.client_row, name="client_row"),
    path("clients/<int:pk>/delete/", views.client_delete, name="client_delete"),
    path("catalog/", views.catalog_list, name="catalog_list"),
    path("catalog/new/", views.catalog_create, name="catalog_create"),
    path("catalog/<int:pk>/edit/", views.catalog_update, name="catalog_update"),
    path("catalog/<int:pk>/row/", views.catalog_row, name="catalog_row"),
    path("catalog/<int:pk>/delete/", views.catalog_delete, name="catalog_delete"),
    path("catalog/<int:pk>/add-to-quote/", views.catalog_add_to_quote, name="catalog_add_to_quote"),
    path("q/<str:token>/", views.public_quote, name="public_quote"),
    path("q/<str:token>/pdf/", views.public_quote_pdf, name="public_quote_pdf"),
]
