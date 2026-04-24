from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    # ==========================================
    # 1. PHÂN HỆ SINH VIÊN (PORTAL)
    # ==========================================
    path('', views.home, name='home'),
    path('tra-cuu/', views.tra_cuu, name='tra_cuu'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Xác thực tài khoản
    path('dang-nhap/', views.dang_nhap, name='dang_nhap'),
    path('dang-xuat/', views.dang_xuat, name='dang_xuat'),
    
    # Thao tác của Sinh viên trên Portal
    path('dang-ky-lop/', views.danh_sach_lop, name='danh_sach_lop'), 
    path('portal/add-cert/', views.quick_add_cert_portal, name='quick_add_cert_portal'),
    path('portal/cert/delete/<int:cert_id>/', views.student_delete_cert, name='student_delete_cert'),
    path('cap-nhat-ho-so/', views.cap_nhat_ho_so, name='cap_nhat_ho_so'),

    # ==========================================
    # 2. PHÂN HỆ QUẢN TRỊ (ADMIN MOFI)
    # ==========================================
    
    # Dashboard tổng & Import
    path('admin-panel/', views.admin_mofi_dashboard, name='admin_mofi_dashboard'),
    path('admin-panel/import-sinh-vien/', views.import_sinh_vien, name='import_sinh_vien'),

    # Quản lý hồ sơ Sinh viên (CRUD)
    path('admin-panel/students/', views.student_list, name='student_list'),
    path('admin-panel/students/add/', views.student_add, name='student_add'),
    path('admin-panel/students/detail/<int:id>/', views.student_detail, name='student_detail'),
    path('admin-panel/students/edit/<int:id>/', views.student_edit, name='student_edit'),
    path('admin-panel/students/delete/<int:id>/', views.student_delete, name='student_delete'),

    # Quản lý Đào tạo & Lớp học
    path('admin-panel/classes/', views.class_list, name='class_list'),
    path('admin-panel/registrations/', views.registration_list, name='registration_list'),
    path('admin-panel/registrations/approve/<int:id>/', views.approve_registration, name='approve_registration'),
    
    # Nhập dữ liệu nhanh từ trang Detail
    path('admin-panel/students/detail/<int:student_id>/add-score/', views.quick_add_diem, name='quick_add_diem'),

    # Trạm kiểm định Chứng chỉ (Staging & Verification)
    path('admin-panel/certificates/', views.certificate_verification_list, name='certificate_verification_list'),
    path('admin-panel/certificates/verify/<int:cert_id>/', views.verify_certificate, name='verify_certificate'),

    # Bổ sung 2 đường dẫn bị thiếu
    path('admin-panel/students/detail/<int:student_id>/add-cert/', views.quick_add_chung_chi, name='quick_add_chung_chi'),
    path('admin-panel/cert/delete/<int:cert_id>/', views.delete_certificate, name='delete_certificate'),
    path('', views.home, name='home'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),

# QUẢN TRỊ MOFI: KHOA
    path('quan-tri/khoa/', views.mofi_khoa_list, name='mofi_khoa_list'),
    path('quan-tri/khoa/them/', views.mofi_khoa_form, name='mofi_khoa_add'),
    path('quan-tri/khoa/sua/<int:pk>/', views.mofi_khoa_form, name='mofi_khoa_edit'),

    # QUẢN TRỊ MOFI: CHỨNG CHỈ
    path('quan-tri/chung-chi/', views.mofi_chungchi_list, name='mofi_chungchi_list'),
    path('quan-tri/chung-chi/them/', views.mofi_chungchi_form, name='mofi_chungchi_add'),
    path('quan-tri/chung-chi/sua/<int:pk>/', views.mofi_chungchi_form, name='mofi_chungchi_edit'),

    # --- QUẢN TRỊ TÀI KHOẢN HỆ THỐNG ---
    path('he-thong/tai-khoan/', views.mofi_user_list, name='mofi_user_list'),
    path('he-thong/tai-khoan/them/', views.mofi_user_form, name='mofi_user_add'),
    path('he-thong/tai-khoan/sua/<int:pk>/', views.mofi_user_form, name='mofi_user_edit'),
   
    # ĐƯỜNG DẪN NHÓM QUYỀN MỚI
    path('he-thong/nhom-quyen/', views.mofi_group_list, name='mofi_group_list'),
    path('he-thong/nhom-quyen/them/', views.mofi_group_form, name='mofi_group_add'),
    path('he-thong/nhom-quyen/sua/<int:pk>/', views.mofi_group_form, name='mofi_group_edit'),
    # Bổ sung vào khu vực QUẢN TRỊ TÀI KHOẢN & HỆ THỐNG
    path('he-thong/tai-khoan/xoa/<int:pk>/', views.mofi_user_delete, name='mofi_user_delete'),
    path('he-thong/nhom-quyen/xoa/<int:pk>/', views.mofi_group_delete, name='mofi_group_delete'),
    path('he-thong/khoa/xoa/<int:pk>/', views.mofi_khoa_delete, name='mofi_khoa_delete'),
    path('he-thong/danh-muc-chung-chi/xoa/<int:pk>/', views.mofi_chungchi_danhmuc_delete, name='mofi_chungchi_danhmuc_delete'),

# Quản trị Đợt thi & Lịch thi
    path('quan-tri/dot-thi/', views.mofi_dot_thi_list, name='mofi_dot_thi_list'),
    path('quan-tri/dot-thi/chi-tiet/<int:dot_thi_id>/', views.mofi_dot_thi_detail, name='mofi_dot_thi_detail'),
    path('quan-tri/dot-thi/import/', views.mofi_import_lich_thi, name='mofi_import_lich_thi'),
    path('quan-tri/dot-thi/import-cntt/', views.mofi_import_diem_cntt, name='mofi_import_diem_cntt'),
    path('quan-tri/dot-thi/import-tdnn/', views.mofi_import_diem_tdnn, name='mofi_import_diem_tdnn'),
    path('quan-tri/dot-thi/import-cdr-nn/', views.mofi_import_diem_cdr_nn, name='mofi_import_diem_cdr_nn'),
    # Nhập Lịch thi kép (Tin học và Ngoại ngữ)
    path('quan-tri/dot-thi/import-lich-thi-cntt/', views.mofi_import_lich_thi_cntt, name='mofi_import_lich_thi_cntt'),
    path('quan-tri/dot-thi/import-lich-thi-nn/', views.mofi_import_lich_thi_nn, name='mofi_import_lich_thi_nn'),
    
    # Logic nghiệp vụ Điểm thi
    path('quan-tri/dot-thi/sua-diem/<int:lich_thi_id>/', views.mofi_sua_diem_thi, name='mofi_sua_diem_thi'),
    path('quan-tri/dot-thi/xuat-excel/<int:dot_thi_id>/', views.mofi_export_bang_diem, name='mofi_export_bang_diem'),
    path('quan-tri/lop-hoc/import/', views.mofi_import_class_list, name='mofi_import_class_list'),
]