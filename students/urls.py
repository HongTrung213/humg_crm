from django.urls import path
from . import views

urlpatterns = [
    # Các đường dẫn cũ
    path('import-excel/', views.import_sinh_vien, name='import_excel'), # (Nếu có)
    path('tra-cuu/', views.tra_cuu, name='tra_cuu'),
    path('lop-boi-duong/', views.danh_sach_lop, name='danh_sach_lop'),
    path('dang-ky-lop/<int:class_id>/', views.dang_ky_lop, name='dang_ky_lop'),
    
    # 2 ĐƯỜNG DẪN MỚI CẦN BỔ SUNG ĐỂ SỬA LỖI
    path('dang-nhap/', views.dang_nhap, name='dang_nhap'),
    path('dang-xuat/', views.dang_xuat, name='dang_xuat'),
]