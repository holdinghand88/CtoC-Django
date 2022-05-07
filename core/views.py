import random
import string

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.auth.hashers import check_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.generic import ListView, DetailView, View, TemplateView
from .forms import PaymentForm, UserDeleteForm
from .models import Item, OrderItem, Order, Payment, UserProfile, Categories, SubCategories, PreviewImageFile
from .utils import *
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


def mypage(request):
    return render(request, "mypage.html")


def products(request):
    context = {
        'items': Item.objects.all()
    }
    return render(request, "products.html", context)


def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


class PurchasedProductView(ListView):
    model = OrderItem
    paginate_by = 8
    template_name = "product_purchased.html"

    def get_queryset(self, **kwargs):
        return OrderItem.objects.filter(user=self.request.user).filter(ordered=True).order_by('-id')


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        context = {
            'order': order,
            'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY
        }

        userprofile = self.request.user.userprofile
        if userprofile.one_click_purchasing:
            # fetch the users card list
            cards = stripe.Customer.list_sources(
                userprofile.stripe_customer_id,
                limit=3,
                object='card'
            )
            card_list = cards['data']
            if len(card_list) > 0:
                # update the context with the default card
                context.update({
                    'card': card_list[0]
                })
                print(card_list[0])
        return render(self.request, "payment.html", context)

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        form = PaymentForm(self.request.POST)
        userprofile = UserProfile.objects.get(user=self.request.user)
        if form.is_valid():
            token = form.cleaned_data.get('stripeToken')
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')

            if save:
                if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
                    # customer = stripe.Customer.retrieve(
                    # userprofile.stripe_customer_id)
                    # customer.sources.create(source=token)

                    customer = stripe.Customer.modify(
                        userprofile.stripe_customer_id,
                        card=token
                    )
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.save()

                else:
                    customer = stripe.Customer.create(
                        email=self.request.user.email,
                        card=token
                    )
                    # customer.sources.create(source=token)
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.one_click_purchasing = True
                    userprofile.save()

            amount = int(order.get_total())

            try:

                if use_default or save:
                    # charge the customer because we cannot charge the token more than once
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency="jpy",
                        customer=userprofile.stripe_customer_id
                    )
                else:
                    # charge once off on the token
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency="jpy",
                        source=token
                    )

                # create the payment
                payment = Payment()
                payment.stripe_charge_id = charge['id']
                payment.user = self.request.user
                payment.amount = order.get_total()
                payment.save()

                # assign the payment to the order

                order_items = order.items.all()
                order_items.update(ordered=True)
                for item in order_items:
                    item.save()

                order.ordered = True
                order.ref_code = create_ref_code()
                order.save()

                #messages.success(self.request, "決済が成功しました!")
                return redirect("core:paymentcomplete")

            except stripe.error.CardError as e:
                body = e.json_body
                err = body.get('error', {})
                messages.warning(self.request, f"{err.get('message')}")
                return redirect("/")

            except stripe.error.RateLimitError as e:
                # Too many requests made to the API too quickly
                messages.warning(self.request, "Rate limit error")
                return redirect("/")

            except stripe.error.InvalidRequestError as e:
                # Invalid parameters were supplied to Stripe's API
                print(e)
                messages.warning(self.request, "Invalid parameters")
                return redirect("/")

            except stripe.error.AuthenticationError as e:
                # Authentication with Stripe's API failed
                # (maybe you changed API keys recently)
                messages.warning(self.request, "認証されていない!")
                return redirect("/")

            except stripe.error.APIConnectionError as e:
                # Network communication with Stripe failed
                messages.warning(self.request, "ネットワークエラー!")
                return redirect("/")

            except stripe.error.StripeError as e:
                # Display a very generic error to the user, and maybe send
                # yourself an email
                messages.warning(
                    self.request, "決済失敗!")
                return redirect("/")

            except Exception as e:
                # send an email to ourselves
                messages.warning(
                    self.request, "決済失敗!")
                return redirect("/")

        messages.warning(self.request, "受信したデータが無効です!")
        return redirect("/payment/stripe/")


def paymentComplete(request):
    context = {}
    return render(request, "payment-complete.html", context)


class HomeView(ListView):
    model = Item
    paginate_by = 8
    template_name = "home.html"

    def get_queryset(self, **kwargs):

        return Item.objects.all().order_by('-id')


class ProductsListView(ListView):
    model = Item
    paginate_by = 8
    template_name = "products.html"

    def get_queryset(self, **kwargs):

        if self.request.GET.get('category_id') or self.request.GET.get('subcategory_id'):
            if self.request.GET.get('category_id'):
                return Item.objects.filter(category_id=int(
                    self.request.GET.get('category_id'))).order_by('-id')
            if self.request.GET.get('subcategory_id'):
                return Item.objects.filter(subcategory__in=[int(
                    self.request.GET.get('subcategory_id'))]).order_by('-id')
        elif self.request.GET.get('category_id') and self.request.GET.get('subcategory_id'):
            return Item.objects.filter(category_id=int(
                self.request.GET.get('category_id'))).filter(subcategory_id=int(
                    self.request.GET.get('subcategory_id'))).order_by('-id')
        else:

            return Item.objects.all().order_by('-id')


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            #messages.warning(self.request, "You do not have an active order")
            return redirect("/")


class ItemDetailView(TemplateView):
    model = Item
    template_name = "product.html"

    def get(self, request, **kwargs):
        slug = kwargs['slug']
        # print(slug)
        item = get_object_or_404(Item, slug=slug)
        image_list = []
        image_list.append(item.image.url)
        pre_imgs = PreviewImageFile.objects.filter(item=item)
        for pre_img in pre_imgs:
            image_list.append(pre_img.image.url)

        context = {
            'object': item,
            'image_list': image_list
        }
        try:
            order_item = OrderItem.objects.filter(
                item=item,
                user=self.request.user,
                ordered=True
            )
            if len(order_item) > 0:
                if settings.DEBUG:
                    file_path = settings.HOST_NAME + item.pdf_file.url
                else:
                    file_path = settings.STATIC_URL + str(item.pdf_file)

                print(file_path)
                context.update({
                    'payment': True,
                    'file_path': file_path
                })
        except:
            pass
        return render(self.request, 'product.html', context)


class CardDetailView(TemplateView):
    model = UserProfile

    def get(self, *args, **kwargs):
        context = {
            'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY
        }
        userprofile = self.request.user.userprofile
        if userprofile.one_click_purchasing:
            # fetch the users card list
            cards = stripe.Customer.list_sources(
                userprofile.stripe_customer_id,
                limit=3,
                object='card'
            )
            card_list = cards['data']
            if len(card_list) > 0:
                # update the context with the default card
                # print(card_list[0])
                context.update({
                    'card': card_list[0]
                })
        return render(self.request, 'card-detail.html', context)

    def post(self, *args, **kwargs):
        form = PaymentForm(self.request.POST)
        userprofile = UserProfile.objects.get(user=self.request.user)
        if form.is_valid():
            token = form.cleaned_data.get('stripeToken')
            print(token)
            if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
                customer = stripe.Customer.modify(
                    userprofile.stripe_customer_id,
                    card=token
                )
                userprofile.stripe_customer_id = customer['id']
                userprofile.save()
                #new_source = customer.sources.create(card=token)
                #customer.default_source = new_source.id
                # customer.save()

            else:
                customer = stripe.Customer.create(
                    email=self.request.user.email,
                    card=token
                )
                # customer.sources.create(source=token)
                userprofile.stripe_customer_id = customer['id']
                userprofile.one_click_purchasing = True
                userprofile.save()

            return redirect("core:carddetailcompleted")
        else:
            return redirect("core:card-detail")


class CloseAccount(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        form = UserDeleteForm()
        return render(self.request, "close_account.html", {'form': form})

    def post(self, request, *args, **kwargs):
        form = UserDeleteForm(request.POST)
        if form.is_valid():
            user = request.user
            confirm_password = form.cleaned_data.get('password')
            if not check_password(confirm_password, user.password):
                messages.success(
                    request, '申し訳なく存じますが、パスワードが間違っています。ご確認お願いします。')
                return render(self.request, "close_account.html", {'form': form})
            else:
                logout(request)
                # user.delete()
                messages.success(request, 'アカウントが削除されました。')
                return redirect("/")
        return render(self.request, "close_account.html", {'form': form})


@login_required
def cardupdatecompleted(request):
    return render(request, "card-detail-completed.html")


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            return redirect("core:order-summary")
        else:
            order.items.add(order_item)
            return redirect("core:order-summary")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            order_item.delete()

            return redirect("core:order-summary")
        else:

            return redirect("core:product", slug=slug)
    else:

        return redirect("core:product", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)

            return redirect("core:order-summary")
        else:

            return redirect("core:product", slug=slug)
    else:

        return redirect("core:product", slug=slug)


def common_search(request):
    search_term = request.GET.get('keyword')
    search_sections = request.GET.get('search_sections')
    results = search_engine(search_term, search_sections)

    html = render_to_string("search_dropdown.html",
                            {'results': results, 'keyword': search_term}, request=request)
    return JsonResponse({'html': html})


def advanced_search(request):
    search_term = request.GET.get('keyword')
    if 'search_sections' in request.GET:
        search_sections = request.GET.getlist('search_sections')
        search_sections = ','.join(search_sections)
    else:
        search_sections = 'items'

    results = search_engine(search_term, search_sections)

    return render(request, "search_result.html", {'results': results, 'keyword': search_term, 'search_sections': search_sections})


def download_result(request):
    id = request.POST.get('id')
    item = get_object_or_404(Item, id=id)
    if settings.PRODUCTION:
        file_path = settings.STATIC_URL + str(item.pdf_file)
    else:
        file_path = settings.HOST_NAME + item.pdf_file.url

    resp = HttpResponse(f'{{"url": "{file_path}"}}')
    resp.status_code = 200
    resp.content_type = "application/json"

    return resp


def get_sub_category(request):
    category_id = request.POST.get('id')
    sub_category = SubCategories.objects.filter(category_id=category_id)
    respond = {
        'id': sub_category.id,
        'name': sub_category.name
    }
    resp = HttpResponse(f'{{"respond": "{respond}"}}')
    resp.status_code = 200
    resp.content_type = "application/json"
    return resp
