from django.contrib import admin
from django.contrib import messages
from .models import SinhVien, DotThi, LichSuThi, ChungChi, LopBoiDuong, DangKyLop

# ==========================================
# 1. CÁC BẢNG CON (INLINES) TRONG HỒ SƠ
# ==========================================

class ChungChiInline(admin.TabularInline):
    model = ChungChi
    extra = 1
    fields = ('loai', 'ten_chung_chi', 'ngay_cap', 'trang_thai', 'file_minh_chung')

class LichSuThiInline(admin.TabularInline):
    model = LichSuThi
    extra = 1
    autocomplete_fields = ['dot_thi']
    fields = ('mon_thi', 'dot_thi', 'diem_thi')


# ==========================================
# 2. ĐĂNG KÝ CÁC BẢNG CHÍNH
# ==========================================

@admin.register(SinhVien)
class SinhVienAdmin(admin.ModelAdmin):
    list_display = ('mssv', 'ho_ten', 'khoa', 'lop')
    search_fields = ('mssv', 'ho_ten')
    list_filter = ('khoa',)
    # Nhúng bảng Điểm thi và Chứng chỉ vào ngay trong hồ sơ sinh viên
    inlines = [LichSuThiInline, ChungChiInline]

# 2. Khai báo bảng con: Lịch sử thi (Inline)
class LichSuThiInline(admin.TabularInline):
    model = LichSuThi
    extra = 1
    autocomplete_fields = ['dot_thi']
    # Bổ sung các cột điểm thành phần vào bảng nhập liệu nhanh
    fields = ('mon_thi', 'dot_thi', 'diem_thanh_phan_1', 'diem_thanh_phan_2', 'diem_thi', 'ket_qua_dat')
    readonly_fields = ('ket_qua_dat',) # Khóa ô này lại, máy tự động tính Đạt/Không đạt

# --- QUẢN LÝ DANH MỤC THI ---
@admin.register(DotThi)
class DotThiAdmin(admin.ModelAdmin):
    list_display = ('ma_dot', 'ten_dot', 'thoi_gian_bat_dau', 'trang_thai', 'diem_chuan_ngoai_ngu', 'diem_chuan_tin_hoc')
    search_fields = ('ma_dot', 'ten_dot')
    
    # Gom nhóm giao diện tạo Đợt thi cho Cán bộ dễ nhìn
    fieldsets = (
        ('Thông tin chung', {
            'fields': ('ma_dot', 'ten_dot', 'thoi_gian_bat_dau', 'thoi_gian_ket_thuc', 'file_thong_bao', 'trang_thai')
        }),
        ('Cấu hình Tiêu chuẩn Ngoại ngữ', {
            'fields': ('diem_chuan_ngoai_ngu', 'diem_liet_ngoai_ngu'),
            'classes': ('collapse',) # Thu gọn lại cho đỡ rối
        }),
        ('Cấu hình Tiêu chuẩn Tin học', {
            'fields': ('diem_chuan_tin_hoc', 'diem_liet_tin_hoc'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LichSuThi)
class LichSuThiAdmin(admin.ModelAdmin):
    list_display = ('sinh_vien', 'mon_thi', 'dot_thi', 'diem_thi', 'ket_qua_dat')
    search_fields = ('sinh_vien__mssv', 'sinh_vien__ho_ten')
    autocomplete_fields = ['sinh_vien', 'dot_thi']
    list_filter = ('mon_thi', 'dot_thi', 'ket_qua_dat')
    readonly_fields = ('ket_qua_dat',)

@admin.register(ChungChi)
class ChungChiAdmin(admin.ModelAdmin):
    list_display = ('sinh_vien', 'ten_chung_chi', 'trang_thai')
    search_fields = ('sinh_vien__mssv',)

@admin.register(LopBoiDuong)
class LopBoiDuongAdmin(admin.ModelAdmin):
    list_display = ('ma_lop', 'ten_lop', 'loai', 'can_bo', 'so_luong_sv', 'si_so_toi_da', 'trang_thai')
    list_filter = ('loai', 'trang_thai', 'can_bo')
    search_fields = ('ma_lop', 'ten_lop')
    
    # Chia giao diện làm 2 khối cho chuyên nghiệp
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('ma_lop', 'ten_lop', 'loai', 'can_bo', 'si_so_toi_da', 'trang_thai')
        }),
        ('Nạp sinh viên vào lớp', {
            'fields': ('file_import_excel', 'sinh_vien'),
            'description': 'Bạn có thể tải file Excel lên (phải có cột ghi chữ MSSV) hoặc tự chọn tay sinh viên ở dưới.'
        }),
    )
    filter_horizontal = ('sinh_vien',)

    # Hàm hiển thị sĩ số thực tế
    def so_luong_sv(self, obj):
        return obj.sinh_vien.count()
    so_luong_sv.short_description = 'Sĩ số hiện tại'

@admin.register(DangKyLop)
class DangKyLopAdmin(admin.ModelAdmin):
    list_display = ('sinh_vien', 'lop_hoc', 'thoi_gian_dk', 'trang_thai')
    list_filter = ('trang_thai', 'lop_hoc')
    search_fields = ('sinh_vien__mssv', 'sinh_vien__ho_ten')
    autocomplete_fields = ['sinh_vien', 'lop_hoc']
    
    # Đăng ký các nút xử lý hàng loạt
    actions = ['duyet_dang_ky', 'huy_dang_ky']

    @admin.action(description='Duyệt các phiếu đăng ký đã chọn')
    def duyet_dang_ky(self, request, queryset):
        for dang_ky in queryset:
            # Kiểm tra xem lớp đã đầy sĩ số chưa
            if dang_ky.lop_hoc.sinh_vien.count() >= dang_ky.lop_hoc.si_so_toi_da:
                self.message_user(request, f"Lớp {dang_ky.lop_hoc.ma_lop} đã đầy, không thể duyệt thêm!", level=messages.ERROR)
            else:
                dang_ky.trang_thai = 'THANH_CONG'
                dang_ky.save() # Tự động gọi hàm save() trong models để nạp sv vào lớp
        self.message_user(request, "Đã hoàn tất duyệt đăng ký.", level=messages.SUCCESS)

    @admin.action(description='Hủy các phiếu đăng ký đã chọn')
    def huy_dang_ky(self, request, queryset):
        queryset.update(trang_thai='DA_HUY')
        for dang_ky in queryset:
            dang_ky.save() # Tự động rút sv khỏi lớp
        self.message_user(request, "Đã hủy các phiếu đăng ký được chọn.", level=messages.WARNING)