
from .models import Category, QuickLink


def navbar_categories(request):
    return {
        'nav_categories': Category.objects.filter(show_on_navbar=True, is_active=True).order_by('name'),
        'quick_links': QuickLink.objects.filter(is_active=True).order_by('order'),
    }
