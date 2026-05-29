
from django.contrib import admin
from .models import ChungChi, DangKyLop, DanhMucChungChi, DotThi, Khoa, LichSuThi, LopBoiDuong, SinhVien, ThongBao


@admin.register(Khoa)
class KhoaAdmin(admin.ModelAdmin):
    list_display = ('id', 'ma_khoa', 'ten_khoa')
    search_fields = ('ma_khoa', 'ten_khoa')
    ordering = ('ma_khoa', 'ten_khoa')


@admin.register(DanhMucChungChi)
class DanhMucChungChiAdmin(admin.ModelAdmin):
    list_display = ('ten_chung_chi', 'loai')
    list_filter = ('loai',)
    search_fields = ('ten_chung_chi',)


@admin.register(SinhVien)
class SinhVienAdmin(admin.ModelAdmin):
    list_display = ('mssv', 'ho_ten', 'khoa', 'lop', 'email_truong', 'dat_chuan_dau_ra')
    list_filter = ('khoa', 'lop')
    search_fields = ('mssv', 'ho_ten', 'email_truong', 'email_ca_nhan')
    readonly_fields = ('dat_chuan_dau_ra', 'check_dat_ngoai_ngu', 'check_dat_tin_hoc')


@admin.register(ChungChi)
class ChungChiAdmin(admin.ModelAdmin):
    list_display = ('sinh_vien', 'danh_muc', 'so_hieu', 'ngay_cap', 'trang_thai', 'ngay_nop')
    list_filter = ('trang_thai', 'danh_muc__loai', 'danh_muc')
    search_fields = ('sinh_vien__mssv', 'sinh_vien__ho_ten', 'so_hieu')
    list_editable = ('trang_thai',)


@admin.register(DotThi)
class DotThiAdmin(admin.ModelAdmin):
    list_display = ('ma_dot', 'ten_dot', 'thoi_gian_bat_dau', 'thoi_gian_ket_thuc')
    search_fields = ('ma_dot', 'ten_dot')


@admin.register(LichSuThi)
class LichSuThiAdmin(admin.ModelAdmin):
    list_display = ('sinh_vien', 'dot_thi', 'mon_thi', 'sbd', 'diem_tong', 'ket_qua_dat')
    list_filter = ('mon_thi', 'ket_qua_dat', 'dot_thi')
    search_fields = ('sinh_vien__mssv', 'sinh_vien__ho_ten', 'sbd')


@admin.register(LopBoiDuong)
class LopBoiDuongAdmin(admin.ModelAdmin):
    list_display = ('ma_lop', 'ten_lop', 'loai', 'si_so_hien_tai', 'si_so_toi_da', 'trang_thai')
    list_filter = ('loai', 'trang_thai')
    search_fields = ('ma_lop', 'ten_lop')
    filter_horizontal = ('sinh_vien',)


@admin.register(DangKyLop)
class DangKyLopAdmin(admin.ModelAdmin):
    list_display = ('sinh_vien', 'lop_hoc', 'trang_thai', 'thoi_gian_dk')
    list_filter = ('trang_thai', 'lop_hoc')
    search_fields = ('sinh_vien__mssv', 'sinh_vien__ho_ten', 'lop_hoc__ten_lop')
    list_editable = ('trang_thai',)


@admin.register(ThongBao)
class ThongBaoAdmin(admin.ModelAdmin):
    list_display = ('tieu_de', 'loai', 'doi_tuong', 'is_active', 'ngay_bat_dau', 'ngay_ket_thuc', 'created_at')
    list_filter = ('loai', 'doi_tuong', 'is_active')
    search_fields = ('tieu_de', 'noi_dung')
    list_editable = ('is_active',)
