from django.contrib import admin
from .models import SinhVien

@admin.register(SinhVien)
class SinhVienAdmin(admin.ModelAdmin):
    # Các cột hiển thị chính
    list_display = ('mssv', 'ho_ten', 'lop', 'status_dau_vao', 'status_ngoai_ngu', 'status_tin_hoc')
    search_fields = ('mssv', 'ho_ten', 'so_dien_thoai')
    list_filter = ('khoa', 'lop', 'has_chung_chi_ngoai_ngu', 'has_chung_chi_tin_hoc')

    # Hiển thị icon xanh/đỏ cho trực quan
    def status_dau_vao(self, obj):
        return obj.check_dat_dau_vao
    status_dau_vao.boolean = True
    status_dau_vao.short_description = 'Đạt Đầu Vào'

    def status_ngoai_ngu(self, obj):
        return obj.check_dat_ngoai_ngu
    status_ngoai_ngu.boolean = True
    status_ngoai_ngu.short_description = 'Đạt CĐR NN'

    def status_tin_hoc(self, obj):
        return obj.check_dat_tin_hoc
    status_tin_hoc.boolean = True
    status_tin_hoc.short_description = 'Đạt CĐR Tin'