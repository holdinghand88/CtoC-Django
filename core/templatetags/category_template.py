from django import template
from core.models import Categories, SubCategories, Order

register = template.Library()


@register.filter
def get_categories(user):
    categories = Categories.objects.all()
    return categories


@register.filter
def get_sub_category(category_id):
    sub_categories = SubCategories.objects.filter(category_id=category_id)
    return sub_categories
