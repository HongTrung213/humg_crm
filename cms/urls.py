
from django.urls import path
from . import views

app_name = 'cms'

urlpatterns = [
    # Public: app đã được include tại /tin-tuc/ trong core/urls.py
    path('', views.post_list, name='post_list'),
    path('bai-viet/<slug:post_slug>/', views.post_detail, name='post_detail'),
    path('danh-muc/<slug:category_slug>/', views.post_list, name='post_by_category'),

    # Quản trị Bài viết
    path('quan-tri/bai-viet/', views.mofi_post_list, name='mofi_post_list'),
    path('quan-tri/bai-viet/them/', views.mofi_post_add, name='mofi_post_add'),
    path('quan-tri/bai-viet/sua/<int:pk>/', views.mofi_post_edit, name='mofi_post_edit'),
    path('quan-tri/bai-viet/xoa/<int:pk>/', views.mofi_post_delete, name='mofi_post_delete'),

    # Quản trị Danh mục
    path('quan-tri/danh-muc/', views.mofi_category_list, name='mofi_category_list'),
    path('quan-tri/danh-muc/them/', views.mofi_category_add, name='mofi_category_add'),
    path('quan-tri/danh-muc/sua/<int:pk>/', views.mofi_category_edit, name='mofi_category_edit'),
    path('quan-tri/danh-muc/xoa/<int:pk>/', views.mofi_category_delete, name='mofi_category_delete'),

    # Slider
    path('quan-tri/slider/', views.mofi_slider_list, name='mofi_slider_list'),
    path('quan-tri/slider/them/', views.mofi_slider_form, name='mofi_slider_add'),
    path('quan-tri/slider/sua/<int:pk>/', views.mofi_slider_form, name='mofi_slider_edit'),
    path('quan-tri/slider/xoa/<int:pk>/', views.mofi_slider_delete, name='mofi_slider_delete'),

    # QuickLink
    path('quan-tri/quicklink/', views.mofi_quicklink_list, name='mofi_quicklink_list'),
    path('quan-tri/quicklink/them/', views.mofi_quicklink_form, name='mofi_quicklink_add'),
    path('quan-tri/quicklink/sua/<int:pk>/', views.mofi_quicklink_form, name='mofi_quicklink_edit'),
    path('quan-tri/quicklink/xoa/<int:pk>/', views.mofi_quicklink_delete, name='mofi_quicklink_delete'),

    # Slug danh mục đặt cuối để không bắt nhầm các route quản trị
    path('<slug:category_slug>/', views.post_list, name='post_list_by_category'),
]
