from django.urls import path
from . import views

app_name = 'cms'

urlpatterns = [
    # Danh sách tất cả
    path('', views.post_list, name='post_list'),
    # Danh sách theo từng danh mục
    path('danh-muc/<slug:category_slug>/', views.post_list, name='post_list_by_category'),
    # Đọc chi tiết bài viết
    path('bai-viet/<slug:post_slug>/', views.post_detail, name='post_detail'),
]