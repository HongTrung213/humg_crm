from .models import Category

def navbar_categories(request):
    # Lấy ra tất cả các danh mục được phép hiển thị trên Menu
    nav_categories = Category.objects.filter(show_on_navbar=True, is_active=True)
    return {'nav_categories': nav_categories}

from .models import Category, QuickLink # Bổ sung import QuickLink

def navbar_categories(request):
    nav_categories = Category.objects.filter(show_on_navbar=True, is_active=True)
    # Lấy thêm danh sách quick links
    quick_links = QuickLink.objects.filter(is_active=True).order_by('order')
    
    return {
        'nav_categories': nav_categories,
        'quick_links': quick_links # Truyền thêm ra toàn hệ thống
    }