from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('tra-cuu/', views.tra_cuu, name='tra_cuu'),
    path('dang-nhap/', views.dang_nhap, name='dang_nhap'),
    path('dang-xuat/', views.dang_xuat, name='dang_xuat'),
    
    # ĐÂY LÀ DÒNG QUAN TRỌNG ĐỂ CÁC NÚT BẤM HOẠT ĐỘNG:
    path('dang-ky-lop/', views.danh_sach_lop, name='danh_sach_lop'), 
    
    path('import-sinh-vien/', views.import_sinh_vien, name='import_sinh_vien'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('cap-nhat-ho-so/', views.cap_nhat_ho_so, name='cap_nhat_ho_so'),
]