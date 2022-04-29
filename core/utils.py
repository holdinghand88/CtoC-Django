from .models import Item, OrderItem, Order, Payment, UserProfile


# Search engine


def search_engine(search_term, search_sections):
    search_sections = search_sections.split(',')

    results = {}
    if 'items' in search_sections:
        items = Item.objects.filter(title__icontains=search_term)

        items = items.order_by('-id')

        results['items_count'] = items.count()

        results['items'] = items

    return results
