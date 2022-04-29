from django.urls import path
from .views import *

app_name = 'core'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('products/', ProductsListView.as_view(), name='products'),
    path('search/', common_search, name='search'),
    path('advanced-search/', advanced_search, name='advanced_search'),
    path('order-summary/', OrderSummaryView.as_view(), name='order-summary'),
    path('product/<slug>/', ItemDetailView.as_view(), name='product'),
    path('add-to-cart/<slug>/', add_to_cart, name='add-to-cart'),
    path('remove-from-cart/<slug>/', remove_from_cart, name='remove-from-cart'),
    path('remove-item-from-cart/<slug>/', remove_single_item_from_cart,
         name='remove-single-item-from-cart'),
    path('payment/<payment_option>/', PaymentView.as_view(), name='payment'),
    path('payment-complete/', paymentComplete, name='paymentcomplete'),
    path('mypage/', mypage, name='mypage'),
    path('purchased-products/', PurchasedProductView.as_view(), name='purchased'),
    path('card-detail/', CardDetailView.as_view(), name='card-detail'),
    path('card-detail-completed/', cardupdatecompleted,
         name='carddetailcompleted'),
    path('close-account/', CloseAccount.as_view(), name='close-account'),
    path('download/', download_result, name='download_result')
]
