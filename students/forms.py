
from django import forms
from django.contrib.auth.models import Group, Permission, User

from .models import CauHinhVaiTro, ChungChi, DanhMucChungChi, Khoa, NganhDaoTao, LopBoiDuong, ThongBao, TieuChiChuanDauRa


# ==============================
# FORM KHOA
# ==============================
class KhoaForm(forms.ModelForm):
    class Meta:
        model = Khoa
        fields = ['ma_khoa', 'ten_khoa']
        widgets = {
            'ma_khoa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'VD: 105, 101, 102...',
            }),
            'ten_khoa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập tên khoa...',
            }),
        }


# ==============================
# FORM NGÀNH ĐÀO TẠO
# ==============================
class NganhDaoTaoForm(forms.ModelForm):
    class Meta:
        model = NganhDaoTao
        fields = [
            'ma_nganh',
            'ten_nganh',
            'khoa',
            'loai_nganh',
            'thoi_gian_dao_tao_nam',
            'is_active',
        ]
        widgets = {
            'ma_nganh': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'VD: 7480201, 7220201...',
            }),
            'ten_nganh': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập tên ngành...',
            }),
            'khoa': forms.Select(attrs={'class': 'form-select'}),
            'loai_nganh': forms.Select(attrs={'class': 'form-select'}),
            'thoi_gian_dao_tao_nam': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5',
                'min': '1',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
            }),
        }


# ==============================
# FORM DANH MỤC CHỨNG CHỈ (MASTER DATA)
# ==============================
class DanhMucChungChiForm(forms.ModelForm):
    class Meta:
        model = DanhMucChungChi
        fields = ['ten_chung_chi', 'loai', 'bac']
        widgets = {
            'ten_chung_chi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: TOEIC, IELTS...'}),
            'loai': forms.Select(attrs={'class': 'form-select'}),
            'bac': forms.Select(attrs={'class': 'form-select'}),
        }

# ==============================
# FORM CHỨNG CHỈ (SINH VIÊN NỘP)
# ==============================
class ChungChiForm(forms.ModelForm):
    class Meta:
        model = ChungChi
        fields = ['danh_muc', 'so_hieu', 'ngay_cap', 'file_minh_chung']
        labels = {
            'danh_muc': 'Chọn loại chứng chỉ',
            'so_hieu': 'Số hiệu / Mã vạch',
            'ngay_cap': 'Ngày cấp trên bằng',
            'file_minh_chung': 'Ảnh hoặc PDF minh chứng',
        }
        widgets = {
            'danh_muc': forms.Select(attrs={'class': 'form-select'}),
            'so_hieu': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập chính xác số hiệu'}),
            'ngay_cap': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'file_minh_chung': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.trang_thai != 'CHO':
            for field in self.fields.values():
                field.disabled = True
            self.fields['file_minh_chung'].help_text = 'Không thể thay đổi file sau khi cán bộ đã xử lý.'

    def clean_file_minh_chung(self):
        file = self.cleaned_data.get('file_minh_chung')
        if file:
            extension = file.name.split('.')[-1].lower()
            if extension not in ['jpg', 'jpeg', 'png', 'pdf']:
                raise forms.ValidationError('Hệ thống chỉ hỗ trợ định dạng JPG, PNG hoặc PDF.')
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Dung lượng file không được vượt quá 5MB.')
        return file


# ==============================
# FORM LỚP BỒI DƯỠNG
# ==============================
class LopBoiDuongForm(forms.ModelForm):
    class Meta:
        model = LopBoiDuong
        fields = [
            'ma_lop', 'ten_lop', 'loai', 'can_bo', 'si_so_toi_da',
            'ngay_khai_giang', 'lich_hoc', 'dia_diem', 'hoc_phi', 'mo_ta', 'trang_thai'
        ]
        widgets = {
            'ma_lop': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: CDRNN-2026-01'}),
            'ten_lop': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên lớp bồi dưỡng...'}),
            'loai': forms.Select(attrs={'class': 'form-select'}),
            'can_bo': forms.Select(attrs={'class': 'form-select'}),
            'si_so_toi_da': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'ngay_khai_giang': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lich_hoc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Tối Thứ 2-4-6, 18:00-20:00'}),
            'dia_diem': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Phòng A101 / Online'}),
            'hoc_phi': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'mo_ta': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Ghi chú nội dung học, đối tượng phù hợp...'}),
            'trang_thai': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


# ==============================
# FORM THÔNG BÁO / CHĂM SÓC SINH VIÊN
# ==============================
class ThongBaoForm(forms.ModelForm):
    class Meta:
        model = ThongBao
        fields = [
            'loai', 'doi_tuong', 'tieu_de', 'noi_dung', 'link_url',
            'ngay_bat_dau', 'ngay_ket_thuc', 'is_active'
        ]
        widgets = {
            'loai': forms.Select(attrs={'class': 'form-select'}),
            'doi_tuong': forms.Select(attrs={'class': 'form-select'}),
            'tieu_de': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tiêu đề thông báo/cảnh báo...'}),
            'noi_dung': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Nhập nội dung hướng dẫn, nhắc việc hoặc tư vấn...'}),
            'link_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'ngay_bat_dau': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ngay_ket_thuc': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('ngay_bat_dau')
        end = cleaned.get('ngay_ket_thuc')
        if start and end and end < start:
            raise forms.ValidationError('Ngày kết thúc không được nhỏ hơn ngày bắt đầu.')
        return cleaned


class UserAccountForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label='Nhóm quyền (Vai trò)',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'groups']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đăng nhập...'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên...'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ và đệm...'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email liên hệ...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


class GroupForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label='Phân bổ các quyền hạn chi tiết',
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Quản trị viên, Giảng viên, Giáo vụ...'}),
        }


class CauHinhVaiTroForm(forms.ModelForm):
    class Meta:
        model = CauHinhVaiTro
        fields = ['user', 'vai_tro', 'duoc_xem_toan_bo', 'khoas_phu_trach', 'ghi_chu', 'is_active']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'vai_tro': forms.Select(attrs={'class': 'form-select'}),
            'duoc_xem_toan_bo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'khoas_phu_trach': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 8}),
            'ghi_chu': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mô tả ngắn phạm vi quyền...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


class TieuChiChuanDauRaForm(forms.ModelForm):
    class Meta:
        model = TieuChiChuanDauRa
        fields = [
            'ten_tieu_chi',
            'loai_chuan',
            'pham_vi_loai_nganh',
            'pham_vi_chuong_trinh',
            'khoa_tuyen_sinh_tu',
            'khoa_tuyen_sinh_den',
            'bac_ngoai_ngu_toi_thieu',
            'thoi_han_hieu_luc_thang',
            'so_chung_chi_mos_toi_thieu',
            'uu_tien',
            'ngay_hieu_luc_tu',
            'ngay_hieu_luc_den',
            'is_active',
            'ghi_chu',
        ]
        widgets = {
            'ten_tieu_chi': forms.TextInput(attrs={'class': 'form-control'}),
            'loai_chuan': forms.Select(attrs={'class': 'form-select'}),
            'pham_vi_loai_nganh': forms.Select(attrs={'class': 'form-select'}),
            'pham_vi_chuong_trinh': forms.Select(attrs={'class': 'form-select'}),
            'khoa_tuyen_sinh_tu': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'khoa_tuyen_sinh_den': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'bac_ngoai_ngu_toi_thieu': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'thoi_han_hieu_luc_thang': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'so_chung_chi_mos_toi_thieu': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'uu_tien': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'ngay_hieu_luc_tu': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ngay_hieu_luc_den': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'ghi_chu': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('ngay_hieu_luc_tu')
        end = cleaned.get('ngay_hieu_luc_den')
        khoa_tu = cleaned.get('khoa_tuyen_sinh_tu')
        khoa_den = cleaned.get('khoa_tuyen_sinh_den')

        if start and end and end < start:
            raise forms.ValidationError('Ngày kết thúc hiệu lực không được nhỏ hơn ngày bắt đầu.')
        if khoa_tu is not None and khoa_den is not None and khoa_den < khoa_tu:
            raise forms.ValidationError('Khóa tuyển sinh đến không được nhỏ hơn khóa tuyển sinh từ.')
        return cleaned
