from django.db.models.signals import post_save
from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.shortcuts import get_object_or_404, reverse, redirect
from django_countries.fields import CountryField
from django.utils.text import slugify
import itertools


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stripe_customer_id = models.CharField(max_length=50, blank=True, null=True)
    one_click_purchasing = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username


class Categories(models.Model):
    name = models.CharField(max_length=256)

    def __str__(self):
        return self.name

    def get_subcategories(self):
        return get_object_or_404(SubCategories, id=self.id)


class SubCategories(models.Model):
    name = models.CharField(max_length=256)
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Item(models.Model):
    title = models.CharField(max_length=100)
    price = models.IntegerField()
    discount_price = models.IntegerField(blank=True, null=True)
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)
    subcategory = models.ManyToManyField(SubCategories)
    seller_name = models.CharField(blank=True, null=True, max_length=256)
    seller_link = models.URLField(blank=True, null=True)
    slug = models.SlugField(default='', editable=False, max_length=256)
    summary = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    publication_date = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to="item_images")
    pdf_file = models.FileField(upload_to="pdf_files")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:product", kwargs={
            'slug': self.slug
        })

    def get_add_to_cart_url(self):
        return reverse("core:add-to-cart", kwargs={
            'slug': self.slug
        })

    def get_remove_from_cart_url(self):
        return reverse("core:remove-from-cart", kwargs={
            'slug': self.slug
        })

    def _generate_slug(self):
        max_length = self._meta.get_field('slug').max_length
        value = self.title
        slug_candidate = slug_original = slugify(value, allow_unicode=True)
        for i in itertools.count(1):
            if not Item.objects.filter(slug=slug_candidate).exists():
                break
            slug_candidate = '{}-{}'.format(slug_original, i)

        self.slug = slug_candidate

    def get_preview_image(self):
        return PreviewImageFile.objects.filter(item_id=self.id)

    def save(self, *args, **kwargs):
        if not self.pk:
            self._generate_slug()
        super().save(*args, **kwargs)


class PreviewImageFile(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="preview_files", blank=True, null=True)


class OrderItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.item.title}の{self.quantity}"

    def get_total_item_price(self):
        return self.quantity * self.item.price

    def get_total_discount_item_price(self):
        return self.quantity * self.item.discount_price

    def get_amount_saved(self):
        return self.get_total_item_price() - self.get_total_discount_item_price()

    def get_final_price(self):
        if self.item.discount_price:
            return self.get_total_discount_item_price()
        return self.get_total_item_price()


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    ref_code = models.CharField(max_length=50, blank=True, null=True)
    items = models.ManyToManyField(OrderItem)
    start_date = models.DateTimeField(auto_now_add=True)
    ordered_date = models.DateTimeField()
    ordered = models.BooleanField(default=False)
    received = models.BooleanField(default=False)

    '''
    1. Item added to cart
    2. Adding a billing address
    (Failed checkout)
    3. Payment
    (Preprocessing, processing, packaging etc.)
    4. Received
    '''

    def __str__(self):
        return self.user.username

    def get_total(self):
        total = 0
        for order_item in self.items.all():
            total += order_item.get_final_price()
        return total


class Payment(models.Model):
    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.SET_NULL, blank=True, null=True)
    amount = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.stipe_charge_id


def userprofile_receiver(sender, instance, created, *args, **kwargs):
    if created:
        userprofile = UserProfile.objects.create(user=instance)


post_save.connect(userprofile_receiver, sender=settings.AUTH_USER_MODEL)
