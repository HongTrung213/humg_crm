from django import forms
from .models import Khoa, DanhMucChungChi, ChungChi
from django.contrib.auth.models import User, Group , Permission


# ==============================
# FORM KHOA
# ==============================
class KhoaForm(forms.ModelForm):
    class Meta:
        model = Khoa
        fields = ['ten_khoa']  # Xóa 'ma_khoa' đi, chỉ để lại 'ten_khoa'
        widgets = {
            'ten_khoa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên khoa...'}),
        }
# ==============================
# FORM DANH MỤC CHỨNG CHỈ (MASTER DATA)
# ==============================
class DanhMucChungChiForm(forms.ModelForm):
    class Meta:
        model = DanhMucChungChi
        fields = ['ten_chung_chi', 'loai']  # Đã xóa 'mo_ta'
        widgets = {
            'ten_chung_chi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: TOEIC, IELTS...'}),
            'loai': forms.Select(attrs={'class': 'form-select'}),
        }

# ==============================
# FORM CHỨNG CHỈ (SINH VIÊN NỘP)
# ==============================
class ChungChiForm(forms.ModelForm):
    class Meta:
        model = ChungChi
        # Thay vì 'loai' và 'ten_chung_chi', ta dùng khóa ngoại 'danh_muc'
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
        super(ChungChiForm, self).__init__(*args, **kwargs)
        # Nếu đang chỉnh sửa một chứng chỉ đã được xử lý (Không phải 'CHO')
        if self.instance and self.instance.pk:
            if self.instance.trang_thai != 'CHO':
                for field in self.fields:
                    self.fields[field].widget.attrs['readonly'] = True
                    self.fields[field].disabled = True
                self.fields['file_minh_chung'].help_text = "Không thể thay đổi file sau khi cán bộ đã xử lý."

    def clean_file_minh_chung(self):
        file = self.cleaned_data.get('file_minh_chung')
        if file:
            extension = file.name.split('.')[-1].lower()
            if extension not in ['jpg', 'jpeg', 'png', 'pdf']:
                raise forms.ValidationError("Hệ thống chỉ hỗ trợ định dạng JPG, PNG hoặc PDF.")
            # Giới hạn dung lượng file (ví dụ 5MB)
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Dung lượng file không được vượt quá 5MB.")
        return file
    

class UserAccountForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label="Nhóm quyền (Vai trò)"
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
        label="Phân bổ các quyền hạn chi tiết"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Quản trị viên, Giảng viên, Giáo vụ...'}),
        }