from django.urls import path
from . import views

urlpatterns = [
    # --- CÁC ĐƯỜNG DẪN CỦA SINH VIÊN (PORTAL) ---
    path('', views.home, name='home'),
    path('tra-cuu/', views.tra_cuu, name='tra_cuu'),
    path('dang-nhap/', views.dang_nhap, name='dang_nhap'),
    path('dang-xuat/', views.dang_xuat, name='dang_xuat'),
    
    path('dang-ky-lop/', views.danh_sach_lop, name='danh_sach_lop'), 
    path('dashboard/', views.dashboard, name='dashboard'),
    path('cap-nhat-ho-so/', views.cap_nhat_ho_so, name='cap_nhat_ho_so'),
    
    # --- CÁC ĐƯỜNG DẪN CỦA CÁN BỘ QUẢN TRỊ (ADMIN MOFI) ---
    
    # TRANG CHỦ ADMIN MOFI (Đã sửa lỗi ở dòng này)
    path('admin-panel/', views.admin_mofi_dashboard, name='admin_mofi_dashboard'),

    # QUẢN LÝ SINH VIÊN & ĐIỂM
    path('admin-panel/students/', views.student_list, name='student_list'),
    path('admin-panel/students/add/', views.student_add, name='student_add'),
    path('admin-panel/students/edit/<int:id>/', views.student_edit, name='student_edit'),
    path('admin-panel/students/delete/<int:id>/', views.student_delete, name='student_delete'),
    
    # IMPORT EXCEL
    path('admin-panel/import-sinh-vien/', views.import_sinh_vien, name='import_sinh_vien'),
]