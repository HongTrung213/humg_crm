from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from .models import SinhVien, ChungChi, DotThi, LichSuThi, LopBoiDuong, DangKyLop, Khoa, DanhMucChungChi

# ==========================================
# 1. QUẢN LÝ DANH MỤC (MASTER DATA)
# ==========================================
@admin.register(Khoa)
class KhoaAdmin(admin.ModelAdmin):
    list_display = ['id', 'ten_khoa']
    search_fields = ['ten_khoa']

@admin.register(DanhMucChungChi)
class DanhMucChungChiAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_loai_display', 'ten_chung_chi']
    list_filter = ['loai']
    search_fields = ['ten_chung_chi']

# ==========================================
# 2. CÁC BẢNG CON (INLINES) TRONG HỒ SƠ SV
# ==========================================
class ChungChiInline(admin.TabularInline):
    model = ChungChi
    extra = 1
    # Dùng trường 'danh_muc' thay vì các trường cũ đã xóa
    fields = ('danh_muc', 'so_hieu', 'ngay_cap', 'trang_thai', 'file_minh_chung')

class LichSuThiInline(admin.TabularInline):
    model = LichSuThi
    extra = 0
    autocomplete_fields = ['dot_thi']
    fields = ('mon_thi', 'dot_thi', 'diem_thanh_phan_1', 'diem_thanh_phan_2', 'diem_thi', 'ket_qua_dat')
    readonly_fields = ['mon_thi', 'diem_tong', 'xep_loai', 'ket_qua_dat']

# ==========================================
# 3. ĐĂNG KÝ CÁC BẢNG CHÍNH
# ==========================================
@admin.register(SinhVien)
class SinhVienAdmin(admin.ModelAdmin):
    list_display = ('mssv', 'ho_ten', 'khoa', 'lop')
    search_fields = ('mssv', 'ho_ten')
    list_filter = ('khoa',)
    inlines = [LichSuThiInline, ChungChiInline]

@admin.register(DotThi)
class DotThiAdmin(admin.ModelAdmin):
    list_display = ('ma_dot', 'ten_dot', 'thoi_gian_bat_dau', 'trang_thai', 'diem_chuan_ngoai_ngu', 'diem_chuan_tin_hoc')
    search_fields = ('ma_dot', 'ten_dot')
    fieldsets = (
        ('Thông tin chung', {
            'fields': ('ma_dot', 'ten_dot', 'thoi_gian_bat_dau', 'thoi_gian_ket_thuc', 'file_thong_bao', 'trang_thai')
        }),
        ('Cấu hình Tiêu chuẩn Ngoại ngữ', {
            'fields': ('diem_chuan_ngoai_ngu', 'diem_liet_ngoai_ngu'),
            'classes': ('collapse',) 
        }),
        ('Cấu hình Tiêu chuẩn Tin học', {
            'fields': ('diem_chuan_tin_hoc', 'diem_liet_tin_hoc'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LichSuThi)
class LichSuThiAdmin(admin.ModelAdmin):
    list_display = ['sinh_vien', 'mon_thi', 'dot_thi', 'diem_tong', 'xep_loai', 'ket_qua_dat']
    search_fields = ('sinh_vien__mssv', 'sinh_vien__ho_ten')
    autocomplete_fields = ['sinh_vien', 'dot_thi']
    list_filter = ('mon_thi', 'dot_thi', 'ket_qua_dat')
    readonly_fields = ['mon_thi', 'diem_tong', 'xep_loai', 'ket_qua_dat']

@admin.register(ChungChi)
class ChungChiAdmin(admin.ModelAdmin):
    list_display = ['sinh_vien', 'danh_muc', 'so_hieu', 'ngay_cap', 'trang_thai']
    search_fields = ['sinh_vien__mssv', 'sinh_vien__ho_ten', 'so_hieu', 'danh_muc__ten_chung_chi']
    list_filter = ['trang_thai', 'danh_muc__loai']

@admin.register(LopBoiDuong)
class LopBoiDuongAdmin(admin.ModelAdmin):
    list_display = ('ma_lop', 'ten_lop', 'loai', 'can_bo', 'so_luong_sv', 'si_so_toi_da', 'trang_thai')
    list_filter = ('loai', 'trang_thai', 'can_bo')
    search_fields = ('ma_lop', 'ten_lop')
    filter_horizontal = ('sinh_vien',)
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('ma_lop', 'ten_lop', 'loai', 'can_bo', 'si_so_toi_da', 'trang_thai')
        }),
        ('Nạp sinh viên vào lớp', {
            'fields': ('file_import_excel', 'sinh_vien'),
            'description': 'Tải file Excel (có cột ghi chữ MSSV) hoặc chọn tay sinh viên.'
        }),
    )

    def so_luong_sv(self, obj):
        return obj.sinh_vien.count()
    so_luong_sv.short_description = 'Sĩ số'

@admin.register(DangKyLop)
class DangKyLopAdmin(admin.ModelAdmin):
    list_display = ('sinh_vien', 'lop_hoc', 'thoi_gian_dk', 'hien_thi_bien_lai', 'trang_thai_mau')
    list_filter = ('trang_thai', 'lop_hoc')
    search_fields = ('sinh_vien__mssv', 'sinh_vien__ho_ten', 'lop_hoc__ten_lop')
    autocomplete_fields = ['sinh_vien', 'lop_hoc']
    actions = ['duyet_dang_ky', 'huy_dang_ky']

    def hien_thi_bien_lai(self, obj):
        if obj.file_minh_chung:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="height: 50px; border-radius: 5px; border: 1px solid #ddd;"/></a>', obj.file_minh_chung.url, obj.file_minh_chung.url)
        return "Trống"
    hien_thi_bien_lai.short_description = 'Biên lai'

    def trang_thai_mau(self, obj):
        colors = {'CHO_DUYET': '#ff9800', 'THANH_CONG': '#28a745', 'DA_HUY': '#dc3545'}
        return format_html('<b style="color: {};">{}</b>', colors.get(obj.trang_thai, 'black'), obj.get_trang_thai_display())
    trang_thai_mau.short_description = 'Trạng thái'

    @admin.action(description='Duyệt các phiếu đã chọn (Nạp vào lớp)')
    def duyet_dang_ky(self, request, queryset):
        count = 0
        for dang_ky in queryset:
            if dang_ky.lop_hoc.sinh_vien.count() < dang_ky.lop_hoc.si_so_toi_da:
                dang_ky.trang_thai = 'THANH_CONG'
                dang_ky.save() 
                count += 1
        self.message_user(request, f"Đã duyệt thành công {count} phiếu đăng ký.")
        
    @admin.action(description='Từ chối / Hủy đăng ký')
    def huy_dang_ky(self, request, queryset):
        queryset.update(trang_thai='DA_HUY')
        self.message_user(request, "Đã hủy các phiếu đăng ký được chọn.")