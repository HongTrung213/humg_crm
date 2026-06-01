import io
import os
import re

import pandas as pd
from openpyxl import load_workbook

from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.html import escape
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission, User
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import LPad
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django.core.paginator import Paginator

from cms.models import Category, Post, QuickLink, Slider
from .forms import DanhMucChungChiForm, GroupForm, KhoaForm, NganhDaoTaoForm, LopBoiDuongForm, ThongBaoForm, UserAccountForm
from .models import (
    ChungChi,
    DangKyLop,
    DanhMucChungChi,
    DotThi,
    Khoa,
    NganhDaoTao,
    LichSuThi,
    LopBoiDuong,
    SinhVien,
    ThongBao,
)


# ==============================================================================
# HÀM TIỆN ÍCH CHUNG
# ==============================================================================
def vi_slugify(text):
    """Chuyển chuỗi tiếng Việt về dạng không dấu, dùng để chuẩn hóa tên cột Excel."""
    text = str(text or '').lower().strip()
    text = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', text)
    text = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', text)
    text = re.sub(r'[ìíịỉĩ]', 'i', text)
    text = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', text)
    text = re.sub(r'[ùúụủũưừứựửữ]', 'u', text)
    text = re.sub(r'[ỳýỵỷỹ]', 'y', text)
    text = re.sub(r'đ', 'd', text)
    return slugify(text)


def normalize_key(text):
    return vi_slugify(text).replace('-', '').replace('_', '')


def clean_excel_val(val):
    if pd.isna(val):
        return ''
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


def to_float(val):
    if val is None or pd.isna(val):
        return None
    txt = str(val).strip().replace(',', '.')
    if not txt:
        return None
    try:
        return float(txt)
    except (TypeError, ValueError):
        return None


def get_khoa_from_mssv(mssv):
    """
    Tự động xác định Khoa từ MSSV HUMG bằng mã khoa lưu trong Database.

    Quy ước hiện dùng:
    - 3 số ở vị trí 4-6 là mã khoa.
    - Ví dụ: 2521050285 -> mã khoa 105.
    """
    mssv_str = str(mssv or '').strip()
    if not mssv_str.isdigit() or len(mssv_str) < 6:
        return None

    ma_khoa = mssv_str[3:6]
    return Khoa.objects.filter(ma_khoa=ma_khoa).first()


def parse_mssv_humg(mssv):
    """
    Hàm tương thích với code cũ.
    Trả về tên khoa nếu tìm thấy trong Database, ngược lại trả về 'Khoa Khác'.
    """
    khoa = get_khoa_from_mssv(mssv)
    return khoa.ten_khoa if khoa else 'Khoa Khác'


def extract_mssv(value):
    """Lấy MSSV từ ô Excel, xử lý cả dạng số, dạng 2121050001.0 hoặc có ký tự thừa."""
    raw = clean_excel_val(value)
    if raw.endswith('.0'):
        raw = raw[:-2]
    digits = re.sub(r'\D', '', raw)
    return digits if len(digits) >= 5 else ''


def find_header_row(df_raw, keywords=None, max_scan=30):
    keywords = keywords or ['mssv', 'masinhvien', 'masv', 'ma sinh vien', 'mã sinh viên']
    normalized_keywords = [normalize_key(k) for k in keywords]
    for i, row in df_raw.head(max_scan).iterrows():
        row_text = ''.join(normalize_key(v) for v in row.values if pd.notna(v))
        if any(k in row_text for k in normalized_keywords):
            return i
    return 0


def normalize_dataframe_columns(df):
    df = df.copy()
    df.columns = [normalize_key(c) for c in df.columns]
    return df


def read_excel_with_smart_header(excel_file, sheet_name=0):
    df_raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
    header_idx = find_header_row(df_raw)
    df = df_raw.iloc[header_idx + 1:].copy()
    df.columns = [normalize_key(c) for c in df_raw.iloc[header_idx]]
    df = df.dropna(how='all')
    return df


def get_visible_sheet_names(excel_file):
    """Trả về danh sách sheet đang visible. Nếu file không đọc được bằng openpyxl thì trả về None."""
    try:
        wb = load_workbook(excel_file, read_only=True, data_only=True)
        visible_sheets = [s.title for s in wb.worksheets if s.sheet_state == 'visible']
        wb.close()
        excel_file.seek(0)
        return visible_sheets
    except Exception:
        try:
            excel_file.seek(0)
        except Exception:
            pass
        return None


def get_first(row, keys, default=''):
    for key in keys:
        norm = normalize_key(key)
        if norm in row and pd.notna(row.get(norm)):
            value = clean_excel_val(row.get(norm))
            if value:
                return value
    return default


def get_float_first(row, keys):
    for key in keys:
        norm = normalize_key(key)
        if norm in row:
            val = to_float(row.get(norm))
            if val is not None:
                return val
    return None


DEFAULT_KHOA_BY_CODE = {
    '100': 'Khoa Khoa học cơ bản',
    '105': 'Khoa Công nghệ thông tin',
}


def clean_office365_value(value):
    """Làm sạch dữ liệu đọc từ Excel Office 365."""
    if value is None or pd.isna(value):
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.lower() in ['nan', 'none', 'null']:
        return ''
    text = text.replace('_x000D_', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_column_value(row, possible_names):
    """Lấy giá trị theo nhiều tên cột khác nhau, có hỗ trợ tiếng Việt có dấu."""
    normalized_map = {normalize_key(key): key for key in row.keys()}
    for name in possible_names:
        lookup = normalize_key(name)
        if lookup in normalized_map:
            return clean_office365_value(row.get(normalized_map[lookup]))
    return ''


def extract_ma_khoa_from_mssv(mssv):
    """Suy mã khoa từ MSSV. Ví dụ: 2521000001 -> 100; 2521050285 -> 105."""
    mssv = extract_mssv(mssv) or clean_office365_value(mssv)
    if mssv.isdigit() and len(mssv) >= 6:
        return mssv[3:6]
    return ''


def get_or_create_khoa_by_mssv(mssv):
    """Lấy hoặc tạo Khoa theo mã khoa trích từ MSSV."""
    ma_khoa = extract_ma_khoa_from_mssv(mssv)
    if not ma_khoa:
        return None
    ten_khoa_mac_dinh = DEFAULT_KHOA_BY_CODE.get(ma_khoa, f'Khoa mã {ma_khoa}')
    khoa, _ = Khoa.objects.get_or_create(
        ma_khoa=ma_khoa,
        defaults={'ten_khoa': ten_khoa_mac_dinh},
    )
    return khoa


def detect_loai_nganh(ten_nganh):
    """Nhận diện ngành đặc biệt dùng cho xét chuẩn ngoại ngữ."""
    text = vi_slugify(clean_office365_value(ten_nganh)).replace('-', ' ')
    if 'ngon ngu anh' in text:
        return 'NGON_NGU_ANH'
    if 'ngon ngu trung' in text or 'trung quoc' in text:
        return 'NGON_NGU_TRUNG'
    return 'THUONG'


def get_or_create_nganh_from_office365(ten_nganh, khoa):
    """Tạo hoặc lấy Ngành đào tạo theo Khoa từ cột NgÀNH."""
    ten_nganh = clean_office365_value(ten_nganh)
    if not ten_nganh:
        return None
    loai_nganh = detect_loai_nganh(ten_nganh)
    nganh, _ = NganhDaoTao.objects.get_or_create(
        khoa=khoa,
        ten_nganh=ten_nganh,
        defaults={
            'loai_nganh': loai_nganh,
            'is_active': True,
        },
    )
    changed_fields = []
    if nganh.loai_nganh != loai_nganh:
        nganh.loai_nganh = loai_nganh
        changed_fields.append('loai_nganh')
    if not nganh.is_active:
        nganh.is_active = True
        changed_fields.append('is_active')
    if changed_fields:
        nganh.save(update_fields=changed_fields)
    return nganh


def extract_khoa_tuyen_sinh(ma_lop):
    """Suy khóa tuyển sinh từ mã lớp. Ví dụ: DCCBNNA70A, CTTTK70 -> 70."""
    text = clean_office365_value(ma_lop).upper()
    numbers = re.findall(r'(\d{2})', text)
    for num in reversed(numbers):
        value = int(num)
        if 50 <= value <= 99:
            return value
    return None


def calculate_nam_nhap_hoc(khoa_tuyen_sinh):
    """Tính năm nhập học. Theo dữ liệu: K69 -> 2024, K70 -> 2025."""
    try:
        return 1955 + int(khoa_tuyen_sinh)
    except (TypeError, ValueError):
        return None


def calculate_nam_du_kien_tot_nghiep(khoa_tuyen_sinh, nganh=None):
    """Tính năm dự kiến tốt nghiệp, mặc định 4 năm nếu ngành chưa cấu hình riêng."""
    nam_nhap_hoc = calculate_nam_nhap_hoc(khoa_tuyen_sinh)
    if not nam_nhap_hoc:
        return None
    thoi_gian_dao_tao = 4.0
    if nganh and getattr(nganh, 'thoi_gian_dao_tao_nam', None):
        thoi_gian_dao_tao = float(nganh.thoi_gian_dao_tao_nam)
    return int(nam_nhap_hoc + thoi_gian_dao_tao)


def normalize_chuong_trinh_dao_tao(ma_lop='', ten_nganh=''):
    """Xác định chương trình đào tạo từ mã lớp hoặc tên ngành."""
    text = vi_slugify(f'{clean_office365_value(ma_lop)} {clean_office365_value(ten_nganh)}').replace('-', ' ')
    if 'chat luong cao' in text or 'clc' in text:
        return 'CHAT_LUONG_CAO'
    if 'tien tien' in text or 'cttt' in text:
        return 'TIEN_TIEN'
    return 'DAI_TRA'



def get_current_sinh_vien(user):
    """Lấy hồ sơ sinh viên hiện tại theo liên kết User, username MSSV hoặc email trường."""
    if not user or not user.is_authenticated:
        return None

    qs = SinhVien.objects.select_related('khoa', 'nganh_dao_tao', 'user')
    sinh_vien = qs.filter(user=user).first()
    if sinh_vien:
        return sinh_vien

    sinh_vien = qs.filter(mssv=user.username).first()
    if sinh_vien:
        if not sinh_vien.user_id:
            sinh_vien.user = user
            sinh_vien.save(update_fields=['user'])
        return sinh_vien

    if user.email:
        sinh_vien = qs.filter(email_truong__iexact=user.email).first()
        if sinh_vien:
            if not sinh_vien.user_id:
                sinh_vien.user = user
                sinh_vien.save(update_fields=['user'])
            return sinh_vien

    return None


def get_thong_bao_for_student(sinh_vien, limit=5):
    """Lấy thông báo/cảnh báo phù hợp với tình trạng chuẩn đầu ra của sinh viên."""
    if not sinh_vien:
        return []
    qs = ThongBao.objects.filter(is_active=True).order_by('-created_at')
    return [tb for tb in qs if tb.phu_hop_voi_sinh_vien(sinh_vien)][:limit]


def ensure_student(mssv, ho_ten='', lop='', khoa_name='', email='', phone='', ten_nganh='', ma_lop=''):
    """Tạo/cập nhật SinhVien + User theo MSSV."""
    mssv = extract_mssv(mssv)
    if not mssv:
        return None

    ho_ten = ho_ten or f'SV_{mssv}'
    khoa_obj = None

    if khoa_name:
        # Nếu file Excel có cột Khoa thì ưu tiên dùng tên khoa trong file.
        # Trường hợp tên khoa chưa có trong danh mục, hệ thống tự tạo bản ghi mới.
        khoa_obj, _ = Khoa.objects.get_or_create(ten_khoa=khoa_name)
    else:
        # Nếu file không có cột Khoa, tự động tra mã khoa từ MSSV theo bảng Danh mục Khoa.
        khoa_obj = get_khoa_from_mssv(mssv)

    if not khoa_obj:
        khoa_obj = get_or_create_khoa_by_mssv(mssv)

    if not khoa_obj:
        khoa_obj, _ = Khoa.objects.get_or_create(ten_khoa='Khoa Khác')

    nganh_obj = get_or_create_nganh_from_office365(ten_nganh, khoa_obj) if ten_nganh else None
    khoa_tuyen_sinh = extract_khoa_tuyen_sinh(ma_lop or lop)
    nam_nhap_hoc = calculate_nam_nhap_hoc(khoa_tuyen_sinh)
    nam_du_kien_tot_nghiep = calculate_nam_du_kien_tot_nghiep(khoa_tuyen_sinh, nganh_obj)
    chuong_trinh = normalize_chuong_trinh_dao_tao(ma_lop or lop, ten_nganh)

    user, user_created = User.objects.get_or_create(
        username=mssv,
        defaults={
            'first_name': ho_ten,
            'email': email or f'{mssv}@student.humg.edu.vn',
            'is_active': True,
        },
    )
    if user_created:
        user.set_password('cfihumg')
    user.first_name = ho_ten
    if email:
        user.email = email
    user.save()

    sv, created = SinhVien.objects.get_or_create(
        mssv=mssv,
        defaults={
            'user': user,
            'ho_ten': ho_ten,
            'lop': lop or None,
            'khoa': khoa_obj,
            'email_truong': email or f'{mssv}@student.humg.edu.vn',
            'so_dien_thoai': phone or None,
            'nganh_dao_tao': nganh_obj,
            'khoa_tuyen_sinh': khoa_tuyen_sinh,
            'nam_nhap_hoc': nam_nhap_hoc,
            'nam_du_kien_tot_nghiep': nam_du_kien_tot_nghiep,
            'chuong_trinh_dao_tao': chuong_trinh,
        },
    )

    changed = False
    if ho_ten and (created or not sv.ho_ten or sv.ho_ten.startswith('SV_')):
        sv.ho_ten = ho_ten
        changed = True
    if lop and sv.lop != lop:
        sv.lop = lop
        changed = True
    if khoa_obj and not sv.khoa:
        sv.khoa = khoa_obj
        changed = True
    if email and sv.email_truong != email:
        sv.email_truong = email
        changed = True
    if phone and sv.so_dien_thoai != phone:
        sv.so_dien_thoai = phone
        changed = True
    if nganh_obj and sv.nganh_dao_tao_id != nganh_obj.id:
        sv.nganh_dao_tao = nganh_obj
        changed = True
    if khoa_tuyen_sinh and sv.khoa_tuyen_sinh != khoa_tuyen_sinh:
        sv.khoa_tuyen_sinh = khoa_tuyen_sinh
        changed = True
    if nam_nhap_hoc and sv.nam_nhap_hoc != nam_nhap_hoc:
        sv.nam_nhap_hoc = nam_nhap_hoc
        changed = True
    if nam_du_kien_tot_nghiep and sv.nam_du_kien_tot_nghiep != nam_du_kien_tot_nghiep:
        sv.nam_du_kien_tot_nghiep = nam_du_kien_tot_nghiep
        changed = True
    if chuong_trinh and sv.chuong_trinh_dao_tao != chuong_trinh:
        sv.chuong_trinh_dao_tao = chuong_trinh
        changed = True
    if not sv.user_id:
        sv.user = user
        changed = True
    if changed:
        sv.save()

    return sv


# ==============================================================================
# 1. PHÂN HỆ CÔNG CỘNG & SINH VIÊN
# ==============================================================================
def home(request):
    slider_posts = Slider.objects.filter(is_active=True).order_by('order')
    quick_links = QuickLink.objects.filter(is_active=True).order_by('order')
    categories_on_home = Category.objects.filter(is_active=True, show_on_homepage=True).order_by('id')

    home_blocks = []
    for cat in categories_on_home:
        posts = Post.objects.filter(category=cat, is_published=True).order_by('-created_at')[:5]
        if posts.exists():
            home_blocks.append({'category': cat, 'posts': posts})

    latest_posts = Post.objects.filter(is_published=True).order_by('-created_at')[:7]
    return render(request, 'students/home.html', {
        'slider_posts': slider_posts,
        'quick_links': quick_links,
        'home_blocks': home_blocks,
        'latest_posts': latest_posts,
    })


def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk, is_published=True)
    post.view_count = (post.view_count or 0) + 1
    post.save(update_fields=['view_count'])
    related_posts = Post.objects.filter(category=post.category, is_published=True).exclude(pk=pk)[:5]
    return render(request, 'students/post_detail.html', {'post': post, 'related_posts': related_posts})


def tra_cuu(request):
    query_mssv = request.GET.get('mssv', '').strip()
    sinh_vien = None
    lich_thi_sap_toi = None
    ket_qua_thi = None
    thong_bao = None

    if query_mssv:
        try:
            sinh_vien = SinhVien.objects.get(mssv=query_mssv)
            toan_bo_lich_thi = sinh_vien.lich_su_thi.select_related('dot_thi').all().order_by('-dot_thi__thoi_gian_bat_dau')
            lich_thi_sap_toi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=True, diem_tong__isnull=True)
            ket_qua_thi = toan_bo_lich_thi.exclude(Q(diem_thanh_phan_1__isnull=True) & Q(diem_tong__isnull=True))
        except SinhVien.DoesNotExist:
            thong_bao = f'Không tìm thấy dữ liệu cho mã số sinh viên: {query_mssv}'

    return render(request, 'students/tra_cuu.html', {
        'sinh_vien': sinh_vien,
        'query_mssv': query_mssv,
        'thong_bao': thong_bao,
        'lich_thi_sap_toi': lich_thi_sap_toi,
        'ket_qua_thi': ket_qua_thi,
    })


def dang_nhap(request):
    if request.method == 'POST':
        username = request.POST.get('mssv') or request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Xin chào {user.first_name or user.username}!')
            next_url = request.GET.get('next')
            return redirect(next_url) if next_url else redirect('students:home')
        messages.error(request, 'Mã sinh viên hoặc mật khẩu không chính xác!')
    return render(request, 'students/login.html')


def dang_xuat(request):
    logout(request)
    messages.info(request, 'Bạn đã đăng xuất thành công.')
    return redirect('students:home')


@login_required
def dashboard(request):
    sinh_vien = get_current_sinh_vien(request.user)
    if not sinh_vien:
        messages.error(request, "Hồ sơ cá nhân chưa được khởi tạo hoặc chưa liên kết với tài khoản đăng nhập.")
        return redirect('students:home')

    ds_dang_ky = DangKyLop.objects.filter(sinh_vien=sinh_vien).select_related('lop_hoc').order_by('-thoi_gian_dk')
    khoas = Khoa.objects.all().order_by('ten_khoa')
    danh_muc_cc = DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi')
    sliders = Slider.objects.filter(is_active=True).order_by('order')
    quick_links = QuickLink.objects.filter(is_active=True).order_by('order')

    toan_bo_lich_thi = sinh_vien.lich_su_thi.select_related('dot_thi').all().order_by('-dot_thi__thoi_gian_bat_dau')
    lich_thi_sap_toi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=True)
    ket_qua_thi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=False)
    thong_bao_moi = get_thong_bao_for_student(sinh_vien, limit=6)

    return render(request, 'students/dashboard.html', {
        'sinh_vien': sinh_vien,
        'ds_dang_ky': ds_dang_ky,
        'khoas': khoas,
        'danh_muc_cc': danh_muc_cc,
        'sliders': sliders,
        'quick_links': quick_links,
        'lich_thi_sap_toi': lich_thi_sap_toi,
        'ket_qua_thi': ket_qua_thi,
        'thong_bao_moi': thong_bao_moi,
    })


@login_required
def nop_chung_chi(request):
    danh_muc_cc = DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi')
    if request.method == 'POST':
        danh_muc_id = request.POST.get('danh_muc_id') or request.POST.get('danh_muc')
        so_hieu = request.POST.get('so_hieu', '').strip()
        ngay_cap = request.POST.get('ngay_cap')
        file_minh_chung = request.FILES.get('file_minh_chung')

        if not danh_muc_id or not so_hieu or not ngay_cap or not file_minh_chung:
            messages.error(request, 'Vui lòng điền đầy đủ thông tin và đính kèm file minh chứng!')
            return redirect('students:nop_chung_chi')

        try:
            sinh_vien = get_current_sinh_vien(request.user)
            if not sinh_vien:
                messages.error(request, 'Không tìm thấy hồ sơ sinh viên liên kết với tài khoản của bạn.')
                return redirect('students:home')
            danh_muc = get_object_or_404(DanhMucChungChi, id=danh_muc_id)
            ChungChi.objects.create(
                sinh_vien=sinh_vien,
                danh_muc=danh_muc,
                so_hieu=so_hieu,
                ngay_cap=ngay_cap,
                file_minh_chung=file_minh_chung,
                trang_thai='CHO',
            )
            messages.success(request, 'Đã gửi yêu cầu xét duyệt chứng chỉ thành công.')
        except SinhVien.DoesNotExist:
            messages.error(request, 'Tài khoản của bạn chưa được liên kết với hồ sơ sinh viên!')
        except IntegrityError:
            messages.error(request, f'Chứng chỉ số hiệu {so_hieu} đã tồn tại trong hồ sơ của bạn.')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra: {e}')
        return redirect('students:nop_chung_chi')

    return render(request, 'students/nop_chung_chi.html', {'danh_muc_cc': danh_muc_cc})


@login_required
def quick_add_cert_portal(request):
    if request.method == 'POST':
        try:
            sinh_vien = get_current_sinh_vien(request.user)
            if not sinh_vien:
                messages.error(request, 'Không tìm thấy hồ sơ sinh viên liên kết với tài khoản của bạn.')
                return redirect('students:home')
            danh_muc = get_object_or_404(DanhMucChungChi, id=request.POST.get('danh_muc_id'))
            ChungChi.objects.create(
                sinh_vien=sinh_vien,
                danh_muc=danh_muc,
                so_hieu=request.POST.get('so_hieu', '').strip(),
                ngay_cap=request.POST.get('ngay_cap'),
                file_minh_chung=request.FILES.get('file_minh_chung'),
                trang_thai='CHO',
            )
            messages.success(request, 'Đã gửi hồ sơ chứng chỉ thành công!')
        except IntegrityError:
            messages.error(request, 'Số hiệu chứng chỉ đã tồn tại trong hồ sơ.')
        except Exception as e:
            messages.error(request, f'Lỗi nộp hồ sơ: {e}')
    return redirect('students:dashboard')


@login_required
def student_delete_cert(request, cert_id):
    sinh_vien = get_current_sinh_vien(request.user)
    if not sinh_vien:
        messages.error(request, 'Không tìm thấy hồ sơ sinh viên liên kết với tài khoản của bạn.')
        return redirect('students:home')
    cert = get_object_or_404(ChungChi, id=cert_id, sinh_vien=sinh_vien)
    if cert.trang_thai == 'CHO':
        if cert.file_minh_chung:
            cert.file_minh_chung.delete(save=False)
        cert.delete()
        messages.success(request, 'Đã hủy hồ sơ thành công.')
    else:
        messages.error(request, 'Hồ sơ đã được xử lý, không thể tự xóa.')
    return redirect('students:dashboard')


@login_required
def cap_nhat_ho_so(request):
    if request.method == 'POST':
        try:
            sinh_vien = get_current_sinh_vien(request.user)
            if not sinh_vien:
                messages.error(request, 'Không tìm thấy hồ sơ sinh viên liên kết với tài khoản của bạn.')
                return redirect('students:home')
            sinh_vien.so_dien_thoai = request.POST.get('so_dien_thoai') or sinh_vien.so_dien_thoai
            sinh_vien.email_ca_nhan = request.POST.get('email_ca_nhan') or sinh_vien.email_ca_nhan
            if request.FILES.get('anh_dai_dien'):
                sinh_vien.anh_dai_dien = request.FILES.get('anh_dai_dien')
            sinh_vien.save()
            messages.success(request, 'Cập nhật thông tin thành công!')
        except SinhVien.DoesNotExist:
            messages.error(request, 'Không tìm thấy hồ sơ sinh viên.')
    return redirect('students:dashboard')


@login_required
def danh_sach_lop(request):
    sinh_vien = get_current_sinh_vien(request.user)
    if not sinh_vien:
        messages.error(request, 'Không tìm thấy hồ sơ sinh viên liên kết với tài khoản của bạn.')
        return redirect('students:home')

    if request.method == 'POST':
        lop_id = request.POST.get('lop_id')
        file_mc = request.FILES.get('file_minh_chung')
        if not lop_id or not file_mc:
            messages.error(request, 'Vui lòng chọn lớp và đính kèm biên lai.')
            return redirect('students:danh_sach_lop')

        lop_hoc = get_object_or_404(LopBoiDuong, id=lop_id, trang_thai=True)
        if DangKyLop.objects.filter(sinh_vien=sinh_vien, lop_hoc=lop_hoc).exists():
            messages.warning(request, 'Bạn đã đăng ký lớp này rồi.')
        else:
            DangKyLop.objects.create(sinh_vien=sinh_vien, lop_hoc=lop_hoc, file_minh_chung=file_mc)
            messages.success(request, f'Đã gửi yêu cầu vào lớp {lop_hoc.ten_lop}.')
        return redirect('students:danh_sach_lop')

    lops = LopBoiDuong.objects.filter(trang_thai=True).order_by('-id')
    da_dang_ky_ids = DangKyLop.objects.filter(sinh_vien=sinh_vien).values_list('lop_hoc_id', flat=True)
    return render(request, 'students/danh_sach_lop.html', {
        'lops': lops,
        'da_dang_ky_ids': da_dang_ky_ids,
        'sinh_vien': sinh_vien,
    })


def quy_che(request):
    return render(request, 'students/quy_che.html')


def lich_thi(request):
    return render(request, 'students/lich_thi.html')


# ==============================================================================
# 2. PHÂN HỆ QUẢN TRỊ: DASHBOARD & HỒ SƠ SINH VIÊN
# ==============================================================================
@staff_member_required
def admin_mofi_dashboard(request):
    tat_ca_sv = SinhVien.objects.select_related('khoa', 'nganh_dao_tao').all()
    sv_canh_bao_nam_cuoi = [sv for sv in tat_ca_sv if getattr(sv, 'tien_do_nam_tu', False)]

    thong_ke_khoa = {}
    danh_sach_chua_dat = []
    for sv in sv_canh_bao_nam_cuoi:
        ten_khoa = sv.khoa.ten_khoa if sv.khoa else 'Chưa phân khoa'
        thong_ke_khoa.setdefault(ten_khoa, {'tong': 0, 'dat': 0, 'chua_dat': 0})
        thong_ke_khoa[ten_khoa]['tong'] += 1
        if getattr(sv, 'chua_dat_chuan_dau_ra', False):
            thong_ke_khoa[ten_khoa]['chua_dat'] += 1
            danh_sach_chua_dat.append(sv)
        else:
            thong_ke_khoa[ten_khoa]['dat'] += 1

    list_thong_ke_khoa = [{'ten_khoa': k, **v} for k, v in thong_ke_khoa.items()]
    list_thong_ke_khoa.sort(key=lambda x: x['tong'], reverse=True)
    danh_sach_chua_dat.sort(key=lambda x: getattr(x, 'nam_nhap_hoc', 9999) or 9999)

    return render(request, 'admin_mofi/pages/dashboard.html', {
        'total_students': tat_ca_sv.count(),
        'active_classes': LopBoiDuong.objects.filter(trang_thai=True).count(),
        'pending_registrations': DangKyLop.objects.filter(trang_thai='CHO_DUYET').count(),
        'certificates_issued': ChungChi.objects.count(),
        'recent_activities': DangKyLop.objects.select_related('sinh_vien', 'lop_hoc').order_by('-thoi_gian_dk')[:5],
        'thong_ke_khoa': list_thong_ke_khoa,
        'so_luong_canh_bao': len(danh_sach_chua_dat),
        'top_canh_bao': danh_sach_chua_dat[:10],
    })


@staff_member_required
def student_list(request):
    query = request.GET.get('q', '').strip()
    sinhviens = SinhVien.objects.select_related('khoa', 'nganh_dao_tao').all().order_by('-mssv')
    if query:
        sinhviens = sinhviens.filter(Q(mssv__icontains=query) | Q(ho_ten__icontains=query) | Q(lop__icontains=query))
    return render(request, 'admin_mofi/students/student_list.html', {'sinhviens': sinhviens, 'query': query})


@staff_member_required
def student_detail(request, id):
    student = get_object_or_404(SinhVien.objects.select_related('khoa', 'nganh_dao_tao'), id=id)
    return render(request, 'admin_mofi/students/student_detail.html', {
        'student': student,
        'ds_dang_ky': student.ds_dang_ky_lop.select_related('lop_hoc').all().order_by('-thoi_gian_dk'),
        'lich_su_thi': student.lich_su_thi.select_related('dot_thi').all().order_by('-ngay_cap_nhat'),
        'danh_muc_cc': DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi'),
        'dot_this': DotThi.objects.all().order_by('-id'),
    })


@staff_member_required
def student_add(request):
    if request.method == 'POST':
        try:
            SinhVien.objects.create(
                mssv=request.POST.get('mssv', '').strip(),
                ho_ten=request.POST.get('ho_ten', '').strip(),
                khoa_id=request.POST.get('khoa') or None,
                lop=request.POST.get('lop', '').strip() or None,
                so_dien_thoai=request.POST.get('so_dien_thoai', '').strip() or None,
                email_ca_nhan=request.POST.get('email_ca_nhan', '').strip() or None,
                email_truong=request.POST.get('email_truong', '').strip() or None,
                anh_dai_dien=request.FILES.get('anh_dai_dien'),
            )
            messages.success(request, 'Thêm sinh viên thành công!')
            return redirect('students:student_list')
        except Exception as e:
            messages.error(request, f'Lỗi thêm sinh viên: {e}')
    return render(request, 'admin_mofi/students/student_form.html', {
        'khoas': Khoa.objects.all(),
        'danh_muc_cc': DanhMucChungChi.objects.all(),
    })


@staff_member_required
def student_edit(request, id):
    student = get_object_or_404(SinhVien, id=id)
    if request.method == 'POST':
        student.khoa_id = request.POST.get('khoa') or None
        student.ho_ten = request.POST.get('ho_ten', student.ho_ten).strip()
        student.lop = request.POST.get('lop', '').strip() or None
        student.so_dien_thoai = request.POST.get('so_dien_thoai', '').strip() or None
        student.email_ca_nhan = request.POST.get('email_ca_nhan', '').strip() or None
        email_truong = request.POST.get('email_truong', '').strip()
        if email_truong:
            student.email_truong = email_truong
        if request.FILES.get('anh_dai_dien'):
            student.anh_dai_dien = request.FILES.get('anh_dai_dien')
        student.save()
        messages.success(request, 'Cập nhật thành công!')
        return redirect('students:student_list')
    return render(request, 'admin_mofi/students/student_form.html', {
        'student': student,
        'khoas': Khoa.objects.all(),
        'danh_muc_cc': DanhMucChungChi.objects.all(),
    })


@staff_member_required
def student_delete(request, id):
    student = get_object_or_404(SinhVien, id=id)
    ten_sv = student.ho_ten
    student.delete()
    messages.success(request, f'Đã xóa hồ sơ của: {ten_sv}')
    return redirect('students:student_list')


@staff_member_required
def import_sinh_vien(request):
    """
    Import danh sách sinh viên từ file Excel dùng cho Office 365.

    Logic chuẩn:
    - MaSV -> lấy mã khoa từ MSSV -> tra bảng Khoa
    - NgÀNH -> tạo/gán Ngành đào tạo thuộc Khoa đó
    - Mã lớp -> lấy khóa tuyển sinh -> xác định năm nhập học + năm dự kiến ra trường
    - UserPrincipalName -> email trường
    - DisplayName -> họ tên
    """
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, 'Vui lòng chọn file Excel.')
            return redirect('students:import_sinh_vien')

        try:
            file_name = (excel_file.name or '').lower()
            if file_name.endswith('.csv'):
                df = pd.read_csv(excel_file)
            else:
                df = pd.read_excel(excel_file)
            df = df.fillna('')
        except Exception as e:
            messages.error(request, f'Không đọc được file dữ liệu: {e}')
            return redirect('students:import_sinh_vien')

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_rows = []

        for index, row in df.iterrows():
            row_dict = row.to_dict()

            mssv = extract_mssv(get_column_value(row_dict, [
                'MaSV', 'MSSV', 'Mã sinh viên', 'Ma sinh vien'
            ]))
            email_truong = get_column_value(row_dict, [
                'UserPrincipalName', 'Email', 'Email trường', 'Email truong'
            ])
            display_name = get_column_value(row_dict, [
                'DisplayName', 'Họ tên', 'Ho ten', 'Họ và tên', 'Ho va ten'
            ])
            ho_lot = get_column_value(row_dict, [
                'HoLotSV', 'Họ lót', 'Ho lot', 'Họ đệm', 'Ho dem'
            ])
            ten_sv = get_column_value(row_dict, [
                'TenSV', 'Tên', 'Ten'
            ])
            ma_lop = get_column_value(row_dict, [
                'Mã lớp', 'Ma lop', 'Lớp', 'Lop'
            ])
            phone = get_column_value(row_dict, [
                'PhoneNumber', 'Số điện thoại', 'So dien thoai', 'SDT', 'SĐT'
            ])
            ten_nganh = get_column_value(row_dict, [
                'NgÀNH', 'Ngành', 'NGÀNH', 'Nganh'
            ])

            if not mssv:
                skipped_count += 1
                error_rows.append(f'Dòng {index + 2}: thiếu MSSV')
                continue

            if not display_name:
                display_name = f'{ho_lot} {ten_sv}'.strip()
            if not display_name:
                skipped_count += 1
                error_rows.append(f'Dòng {index + 2}: thiếu họ tên')
                continue

            if not email_truong:
                email_truong = f'{mssv}@student.humg.edu.vn'

            try:
                existed = SinhVien.objects.filter(mssv=mssv).exists()
                sv = ensure_student(
                    mssv=mssv,
                    ho_ten=display_name,
                    lop=ma_lop,
                    email=email_truong,
                    phone=phone,
                    ten_nganh=ten_nganh,
                    ma_lop=ma_lop,
                )
                if sv:
                    if existed:
                        updated_count += 1
                    else:
                        created_count += 1
                else:
                    skipped_count += 1
                    error_rows.append(f'Dòng {index + 2}: không thể tạo/cập nhật sinh viên')
            except Exception as e:
                skipped_count += 1
                error_rows.append(f'Dòng {index + 2}: {e}')

        if error_rows:
            request.session['last_import_errors'] = error_rows[:100]

        messages.success(
            request,
            f'Import hoàn tất. Thêm mới: {created_count}, cập nhật: {updated_count}, bỏ qua: {skipped_count}.'
        )
        return redirect('students:student_list')

    return render(request, 'admin_mofi/students/import_excel.html')


def import_students_office365(request):
    return import_sinh_vien(request)


# ==============================================================================
# 3. QUẢN LÝ LỚP HỌC & CHỨNG CHỈ
# ==============================================================================
@staff_member_required
def class_list(request):
    return render(request, 'admin_mofi/pages/class_list.html', {
        'classes': LopBoiDuong.objects.all().order_by('-id'),
    })


@staff_member_required
def class_form(request, pk=None):
    instance = get_object_or_404(LopBoiDuong, pk=pk) if pk else None
    if request.method == 'POST':
        form = LopBoiDuongForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã lưu thông tin lớp bồi dưỡng thành công.')
            return redirect('students:class_list')
    else:
        form = LopBoiDuongForm(instance=instance)
    return render(request, 'admin_mofi/pages/class_form.html', {
        'form': form,
        'instance': instance,
    })


@staff_member_required
def class_delete(request, pk):
    lop = get_object_or_404(LopBoiDuong, pk=pk)
    ten_lop = lop.ten_lop
    lop.delete()
    messages.success(request, f'Đã xóa lớp "{ten_lop}".')
    return redirect('students:class_list')




@staff_member_required
def class_export_students(request, pk):
    """Xuất danh sách sinh viên đã được duyệt vào lớp ra Excel."""
    lop = get_object_or_404(LopBoiDuong, pk=pk)
    students = lop.sinh_vien.select_related('khoa').all().order_by('mssv')

    rows = []
    for idx, sv in enumerate(students, start=1):
        rows.append({
            'STT': idx,
            'MSSV': sv.mssv,
            'Họ và tên': sv.ho_ten,
            'Lớp': sv.lop or '',
            'Khoa/Viện': sv.khoa.ten_khoa if sv.khoa else '',
            'Email trường': sv.email_truong or '',
            'Số điện thoại': sv.so_dien_thoai or '',
            'Đạt ngoại ngữ': 'Đạt' if sv.check_dat_ngoai_ngu else 'Chưa đạt',
            'Đạt tin học': 'Đạt' if sv.check_dat_tin_hoc else 'Chưa đạt',
            'Đạt CĐR': 'Đạt' if sv.dat_chuan_dau_ra else 'Chưa đạt',
        })

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['STT', 'MSSV', 'Họ và tên', 'Lớp', 'Khoa/Viện', 'Email trường', 'Số điện thoại', 'Đạt ngoại ngữ', 'Đạt tin học', 'Đạt CĐR'])

    safe_name = re.sub(r'[^A-Za-z0-9_-]+', '_', lop.ma_lop or f'lop_{lop.pk}')
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="danh_sach_{safe_name}.xlsx"'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Danh sach lop')
        ws = writer.sheets['Danh sach lop']
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 35)

    return response

@staff_member_required
def registration_list(request):
    regs = DangKyLop.objects.select_related('sinh_vien', 'lop_hoc').all().order_by(
        Case(
            When(trang_thai='CHO_DUYET', then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        '-thoi_gian_dk',
    )
    return render(request, 'admin_mofi/classes/registration_list.html', {'registrations': regs})


@staff_member_required
def approve_registration(request, id):
    reg = get_object_or_404(DangKyLop, id=id)
    if request.method == 'POST':
        action = request.POST.get('action')
        reg.trang_thai = 'THANH_CONG' if action == 'approve' else 'DA_HUY'
        reg.save()
        messages.success(request, 'Xử lý đăng ký thành công.')
    return redirect('students:registration_list')


@staff_member_required
def mofi_import_class_list(request):
    if request.method == 'POST':
        lop_id = request.POST.get('lop_id')
        excel_file = request.FILES.get('excel_file')
        if not excel_file or not lop_id:
            messages.error(request, 'Vui lòng chọn lớp học và file Excel.')
            return redirect('students:mofi_import_class_list')

        lop_hoc = get_object_or_404(LopBoiDuong, id=lop_id)
        try:
            df = read_excel_with_smart_header(excel_file)
            count = 0
            for _, row in df.iterrows():
                mssv = extract_mssv(get_first(row, ['mssv', 'ma sinh vien', 'masinhvien']))
                if not mssv:
                    continue
                sv = SinhVien.objects.filter(mssv=mssv).first()
                if not sv:
                    ho_ten = get_first(row, ['hoten', 'ho ten', 'hovaten', 'ten sinh vien'])
                    lop = get_first(row, ['lop', 'lop sinh hoat'])
                    sv = ensure_student(mssv, ho_ten=ho_ten, lop=lop)
                DangKyLop.objects.update_or_create(
                    sinh_vien=sv,
                    lop_hoc=lop_hoc,
                    defaults={'trang_thai': 'THANH_CONG'},
                )
                count += 1
            messages.success(request, f'Đã thêm {count} sinh viên vào lớp {lop_hoc.ten_lop}.')
            return redirect('students:class_list')
        except Exception as e:
            messages.error(request, f'Lỗi xử lý file Excel: {e}')

    return render(request, 'admin_mofi/pages/import_class_list.html', {
        'lops': LopBoiDuong.objects.filter(trang_thai=True).order_by('-id'),
    })


@staff_member_required
def quick_add_chung_chi(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(SinhVien, id=student_id)
        danh_muc = get_object_or_404(DanhMucChungChi, id=request.POST.get('danh_muc_id'))
        so_hieu = request.POST.get('so_hieu', '').strip()
        try:
            ChungChi.objects.create(
                sinh_vien=student,
                danh_muc=danh_muc,
                so_hieu=so_hieu,
                ngay_cap=request.POST.get('ngay_cap'),
                file_minh_chung=request.FILES.get('file_minh_chung'),
                trang_thai='CHO',
            )
            messages.success(request, 'Đã tải lên chứng chỉ mới thành công.')
        except IntegrityError:
            messages.error(request, f"Chứng chỉ mang số hiệu '{so_hieu}' đã tồn tại trong hồ sơ của sinh viên này.")
    return redirect('students:student_detail', id=student_id)


@staff_member_required
def certificate_verification_list(request):
    pending_certs = ChungChi.objects.filter(trang_thai='CHO').select_related('sinh_vien', 'danh_muc').order_by('ngay_nop')
    return render(request, 'admin_mofi/certificates/cert_list.html', {'pending_certs': pending_certs})


@staff_member_required
def verify_certificate(request, cert_id):
    cert = get_object_or_404(ChungChi, id=cert_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        ghi_chu = request.POST.get('ghi_chu', '').strip()
        if action == 'approve':
            cert.trang_thai = 'DAT'
            cert.ghi_chu_xac_minh = ghi_chu or 'Chứng chỉ hợp lệ.'
            cert.save()
            messages.success(request, f'Đã duyệt chứng chỉ cho {cert.sinh_vien.ho_ten}.')
        elif action == 'reject':
            cert.trang_thai = 'KHONG_DAT'
            cert.ghi_chu_xac_minh = ghi_chu or 'Thông tin chưa chính xác.'
            cert.save()
            messages.warning(request, f'Đã từ chối hồ sơ của {cert.sinh_vien.ho_ten}.')
        elif action == 'delete':
            ten_sv = cert.sinh_vien.ho_ten
            if cert.file_minh_chung:
                cert.file_minh_chung.delete(save=False)
            cert.delete()
            messages.error(request, f'Đã xóa file/hồ sơ chứng chỉ của {ten_sv}.')
    return redirect(request.META.get('HTTP_REFERER', reverse('students:certificate_verification_list')))


@staff_member_required
def delete_certificate(request, cert_id):
    cert = get_object_or_404(ChungChi, id=cert_id)
    ten_sv = cert.sinh_vien.ho_ten
    if cert.file_minh_chung:
        cert.file_minh_chung.delete(save=False)
    cert.delete()
    messages.success(request, f'Đã xóa chứng chỉ của {ten_sv}.')
    return redirect(request.META.get('HTTP_REFERER', reverse('students:certificate_verification_list')))


# ==============================================================================
# 4. MASTER DATA: KHOA, DANH MỤC CHỨNG CHỈ, USER, GROUP
# ==============================================================================
@staff_member_required
def mofi_khoa_list(request):
    query = request.GET.get('q', '').strip()
    danh_sach_khoa = Khoa.objects.all().order_by('ma_khoa', 'ten_khoa')
    if query:
        danh_sach_khoa = danh_sach_khoa.filter(
            Q(ma_khoa__icontains=query) | Q(ten_khoa__icontains=query)
        )
    return render(request, 'admin_mofi/pages/khoa_list.html', {
        'danh_sach_khoa': danh_sach_khoa,
        'query': query,
    })


@staff_member_required
def mofi_khoa_form(request, pk=None):
    instance = get_object_or_404(Khoa, pk=pk) if pk else None
    if request.method == 'POST':
        form = KhoaForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật thông tin Khoa thành công!')
            return redirect('students:mofi_khoa_list')
    else:
        form = KhoaForm(instance=instance)
    return render(request, 'admin_mofi/pages/khoa_form.html', {'form': form, 'instance': instance})


@staff_member_required
def mofi_khoa_delete(request, pk):
    get_object_or_404(Khoa, pk=pk).delete()
    messages.success(request, 'Đã xóa Khoa thành công.')
    return redirect('students:mofi_khoa_list')


@staff_member_required
def mofi_nganh_list(request):
    query = request.GET.get('q', '').strip()
    ds_nganh = NganhDaoTao.objects.select_related('khoa').all().order_by('khoa__ma_khoa', 'ten_nganh')
    if query:
        ds_nganh = ds_nganh.filter(
            Q(ma_nganh__icontains=query) |
            Q(ten_nganh__icontains=query) |
            Q(khoa__ma_khoa__icontains=query) |
            Q(khoa__ten_khoa__icontains=query)
        )
    return render(request, 'admin_mofi/pages/nganh_list.html', {
        'ds_nganh': ds_nganh,
        'query': query,
    })


@staff_member_required
def mofi_nganh_form(request, pk=None):
    instance = get_object_or_404(NganhDaoTao, pk=pk) if pk else None
    if request.method == 'POST':
        form = NganhDaoTaoForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã lưu ngành đào tạo thành công.')
            return redirect('students:mofi_nganh_list')
    else:
        form = NganhDaoTaoForm(instance=instance)
    return render(request, 'admin_mofi/pages/nganh_form.html', {
        'form': form,
        'instance': instance,
    })


@staff_member_required
def mofi_nganh_delete(request, pk):
    nganh = get_object_or_404(NganhDaoTao, pk=pk)
    ten_nganh = nganh.ten_nganh
    nganh.delete()
    messages.success(request, f'Đã xóa ngành đào tạo: {ten_nganh}')
    return redirect('students:mofi_nganh_list')


@staff_member_required
def mofi_chungchi_list(request):
    query = request.GET.get('q', '').strip()
    danh_sach = DanhMucChungChi.objects.all().order_by('-id')
    if query:
        danh_sach = danh_sach.filter(Q(ten_chung_chi__icontains=query) | Q(loai__icontains=query))
    return render(request, 'admin_mofi/pages/chungchi_list.html', {'danh_sach': danh_sach, 'query': query})


@staff_member_required
def mofi_chungchi_form(request, pk=None):
    instance = get_object_or_404(DanhMucChungChi, pk=pk) if pk else None
    if request.method == 'POST':
        form = DanhMucChungChiForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật danh mục chứng chỉ thành công!')
            return redirect('students:mofi_chungchi_list')
    else:
        form = DanhMucChungChiForm(instance=instance)
    return render(request, 'admin_mofi/pages/chungchi_form.html', {'form': form, 'instance': instance})


@staff_member_required
def mofi_chungchi_danhmuc_delete(request, pk):
    get_object_or_404(DanhMucChungChi, pk=pk).delete()
    messages.success(request, 'Đã xóa Danh mục Chứng chỉ thành công.')
    return redirect('students:mofi_chungchi_list')


@staff_member_required
def mofi_user_list(request):
    users = User.objects.all().prefetch_related('groups').order_by('-date_joined')
    return render(request, 'admin_mofi/system/user_list.html', {'users': users})


@staff_member_required
def mofi_user_form(request, pk=None):
    instance = get_object_or_404(User, pk=pk) if pk else None
    if request.method == 'POST':
        form = UserAccountForm(request.POST, instance=instance)
        if form.is_valid():
            user = form.save(commit=False)
            if not pk:
                user.set_password('Humg@123456')
                user.is_staff = True
            user.save()
            form.save_m2m()
            messages.success(request, 'Cập nhật tài khoản thành công!')
            return redirect('students:mofi_user_list')
    else:
        form = UserAccountForm(instance=instance)
    return render(request, 'admin_mofi/system/user_form.html', {'form': form, 'instance': instance})


@staff_member_required
def mofi_user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.is_superuser:
        messages.error(request, 'Không thể xóa tài khoản SuperAdmin.')
    else:
        user.delete()
        messages.success(request, 'Đã xóa tài khoản cán bộ thành công.')
    return redirect('students:mofi_user_list')


@staff_member_required
def mofi_group_list(request):
    return render(request, 'admin_mofi/system/group_list.html', {'groups': Group.objects.all().order_by('name')})


@staff_member_required
def mofi_group_form(request, pk=None):
    instance = get_object_or_404(Group, pk=pk) if pk else None
    if request.method == 'POST':
        form = GroupForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật Nhóm quyền thành công!')
            return redirect('students:mofi_group_list')
    else:
        form = GroupForm(instance=instance)
    return render(request, 'admin_mofi/system/group_form.html', {'form': form, 'instance': instance})


@staff_member_required
def mofi_group_delete(request, pk):
    get_object_or_404(Group, pk=pk).delete()
    messages.success(request, 'Đã xóa Nhóm quyền thành công.')
    return redirect('students:mofi_group_list')



# ==============================================================================
# 4.5. CHĂM SÓC SINH VIÊN - THÔNG BÁO/CẢNH BÁO
# ==============================================================================
@staff_member_required
def mofi_thongbao_list(request):
    query = request.GET.get('q', '').strip()
    loai = request.GET.get('loai', '').strip()
    doi_tuong = request.GET.get('doi_tuong', '').strip()

    notifications = ThongBao.objects.select_related('created_by').all().order_by('-created_at')

    if query:
        notifications = notifications.filter(
            Q(tieu_de__icontains=query) |
            Q(noi_dung__icontains=query) |
            Q(link_url__icontains=query)
        )
    if loai:
        notifications = notifications.filter(loai=loai)
    if doi_tuong:
        notifications = notifications.filter(doi_tuong=doi_tuong)

    context = {
        'notifications': notifications,
        'thong_baos': notifications,
        'query': query,
        'loai': loai,
        'doi_tuong': doi_tuong,
        'loai_choices': ThongBao.LOAI_THONG_BAO,
        'doi_tuong_choices': ThongBao.DOI_TUONG,
        'tong_thong_bao': ThongBao.objects.count(),
        'dang_hien_thi': ThongBao.objects.filter(is_active=True).count(),
        'tong_sv_chua_dat_nn': sum(1 for sv in SinhVien.objects.all() if not sv.check_dat_ngoai_ngu),
        'tong_sv_chua_dat_th': sum(1 for sv in SinhVien.objects.all() if not sv.check_dat_tin_hoc),
    }
    return render(request, 'admin_mofi/pages/thongbao_list.html', context)


@staff_member_required
def mofi_thongbao_form(request, pk=None):
    instance = get_object_or_404(ThongBao, pk=pk) if pk else None

    if request.method == 'POST':
        form = ThongBaoForm(request.POST, instance=instance)
        if form.is_valid():
            thong_bao = form.save(commit=False)
            if not thong_bao.created_by_id:
                thong_bao.created_by = request.user
            thong_bao.save()
            messages.success(request, 'Đã lưu thông báo/cảnh báo sinh viên thành công.')
            return redirect('students:mofi_thongbao_list')
    else:
        form = ThongBaoForm(instance=instance)

    return render(request, 'admin_mofi/pages/thongbao_form.html', {
        'form': form,
        'instance': instance,
    })


@staff_member_required
@require_POST
def mofi_thongbao_delete(request, pk):
    thong_bao = get_object_or_404(ThongBao, pk=pk)
    title = thong_bao.tieu_de
    thong_bao.delete()
    messages.success(request, f'Đã xóa thông báo "{title}".')
    return redirect('students:mofi_thongbao_list')




def _get_thongbao_student_recipients(thong_bao):
    """
    Lấy danh sách email sinh viên theo đối tượng nhận của thông báo.

    Ưu tiên email trường; nếu không có thì dùng email cá nhân.
    Danh sách email được loại trùng và chuẩn hóa chữ thường.
    """
    students = SinhVien.objects.select_related('khoa', 'nganh_dao_tao').all()
    recipients = []

    for sv in students:
        is_target = False

        if thong_bao.doi_tuong == 'ALL':
            is_target = True
        elif thong_bao.doi_tuong == 'CHUA_DAT_NN':
            is_target = not sv.check_dat_ngoai_ngu
        elif thong_bao.doi_tuong == 'CHUA_DAT_TH':
            is_target = not sv.check_dat_tin_hoc
        elif thong_bao.doi_tuong == 'CHUA_DAT_CDR':
            is_target = not sv.dat_chuan_dau_ra
        elif thong_bao.doi_tuong == 'NAM_CUOI':
            is_target = sv.tien_do_nam_tu

        if not is_target:
            continue

        email = (sv.email_truong or sv.email_ca_nhan or '').strip().lower()
        if email:
            recipients.append(email)

    return sorted(set(recipients))


@staff_member_required
@require_POST
def mofi_thongbao_send_email(request, pk):
    """
    Gửi email thông báo/cảnh báo tới nhóm sinh viên phù hợp.

    Cơ chế gửi:
    - Chỉ gửi thông báo đang bật và đang hiệu lực.
    - Lọc người nhận theo trường doi_tuong của ThongBao.
    - Gửi theo lô bằng BCC để không lộ danh sách email sinh viên.
    """
    thong_bao = get_object_or_404(ThongBao, pk=pk)

    if not thong_bao.is_active:
        messages.error(request, 'Thông báo này đang tắt hiển thị, không thể gửi email.')
        return redirect('students:mofi_thongbao_list')

    if hasattr(thong_bao, 'dang_hieu_luc') and not thong_bao.dang_hieu_luc():
        messages.error(request, 'Thông báo này chưa đến ngày hiệu lực hoặc đã hết hạn, không thể gửi email.')
        return redirect('students:mofi_thongbao_list')

    recipients = _get_thongbao_student_recipients(thong_bao)

    if not recipients:
        messages.warning(request, 'Không tìm thấy email sinh viên phù hợp để gửi.')
        return redirect('students:mofi_thongbao_list')

    subject = f'[HUMG CFI] {thong_bao.tieu_de}'
    safe_title = escape(thong_bao.tieu_de)
    safe_content = escape(thong_bao.noi_dung)
    safe_link = escape(thong_bao.link_url or '')

    plain_body = f"""Kính gửi sinh viên,

Trung tâm Ngoại ngữ - Tin học HUMG gửi tới bạn thông báo sau:

{thong_bao.tieu_de}

{thong_bao.noi_dung}

{('Xem thêm tại: ' + thong_bao.link_url) if thong_bao.link_url else ''}

Trân trọng,
Trung tâm Ngoại ngữ - Tin học HUMG
Trường Đại học Mỏ - Địa chất
"""

    html_body = f"""
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #222; line-height: 1.6;">
    <p>Kính gửi sinh viên,</p>
    <p>Trung tâm Ngoại ngữ - Tin học HUMG gửi tới bạn thông báo sau:</p>

    <div style="border-left: 4px solid #0d6efd; padding: 12px 16px; background: #f8f9fa; margin: 16px 0;">
        <h3 style="margin: 0 0 10px 0; color: #0d6efd;">{safe_title}</h3>
        <p style="margin: 0; white-space: pre-line;">{safe_content}</p>
    </div>
"""

    if thong_bao.link_url:
        html_body += f"""
    <p>
        <a href="{safe_link}"
           style="display: inline-block; padding: 10px 16px; background: #0d6efd; color: #fff; text-decoration: none; border-radius: 4px;">
            Xem thông tin liên quan
        </a>
    </p>
"""

    html_body += """
    <p>Trân trọng,</p>
    <p>
        <strong>Trung tâm Ngoại ngữ - Tin học HUMG</strong><br>
        Trường Đại học Mỏ - Địa chất
    </p>
</div>
"""

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@humg.edu.vn')
    batch_size = 50
    sent_count = 0

    try:
        for start in range(0, len(recipients), batch_size):
            batch = recipients[start:start + batch_size]

            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_body,
                from_email=from_email,
                to=[from_email],
                bcc=batch,
            )
            email.attach_alternative(html_body, 'text/html')
            email.send(fail_silently=False)
            sent_count += len(batch)

        messages.success(request, f'Đã gửi email thông báo tới {sent_count} sinh viên.')

    except Exception as e:
        messages.error(request, f'Lỗi khi gửi email: {e}')

    return redirect('students:mofi_thongbao_list')


@staff_member_required
def mofi_export_chua_dat_chuan(request):
    """Xuất danh sách sinh viên chưa đạt chuẩn đầu ra để cán bộ chăm sóc/nhắc việc."""
    students = SinhVien.objects.select_related('khoa', 'nganh_dao_tao').all().order_by('khoa__ten_khoa', 'lop', 'mssv')
    rows = []

    for sv in students:
        dat_nn = sv.check_dat_ngoai_ngu
        dat_th = sv.check_dat_tin_hoc
        if dat_nn and dat_th:
            continue

        ly_do = []
        if not dat_nn:
            ly_do.append('Chưa đạt Ngoại ngữ')
        if not dat_th:
            ly_do.append('Chưa đạt Tin học')

        rows.append({
            'STT': len(rows) + 1,
            'MSSV': sv.mssv,
            'Họ và tên': sv.ho_ten,
            'Lớp': sv.lop or '',
            'Khoa/Viện': sv.khoa.ten_khoa if sv.khoa else '',
            'Email trường': sv.email_truong or '',
            'Email cá nhân': sv.email_ca_nhan or '',
            'Số điện thoại': sv.so_dien_thoai or '',
            'Năm cuối': 'Có' if sv.tien_do_nam_tu else 'Không',
            'Ngoại ngữ': 'Đạt' if dat_nn else 'Chưa đạt',
            'Tin học': 'Đạt' if dat_th else 'Chưa đạt',
            'Nội dung cần chăm sóc': '; '.join(ly_do),
        })

    columns = ['STT', 'MSSV', 'Họ và tên', 'Lớp', 'Khoa/Viện', 'Email trường', 'Email cá nhân', 'Số điện thoại', 'Năm cuối', 'Ngoại ngữ', 'Tin học', 'Nội dung cần chăm sóc']
    df = pd.DataFrame(rows, columns=columns)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"danh_sach_chua_dat_chuan_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Chua dat CDR')
        ws = writer.sheets['Chua dat CDR']
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    return response


# ==============================================================================
# 5. QUẢN LÝ ĐỢT THI, LỊCH THI, ĐIỂM THI
# ==============================================================================
@staff_member_required
def mofi_dot_thi_list(request):
    if request.method == 'POST':
        try:
            thoi_gian_bat_dau = request.POST.get('thoi_gian_bat_dau')
            thoi_gian_ket_thuc = request.POST.get('thoi_gian_ket_thuc')
            DotThi.objects.create(
                ma_dot=request.POST.get('ma_dot', '').strip(),
                ten_dot=request.POST.get('ten_dot', '').strip(),
                thoi_gian_bat_dau=parse_datetime(thoi_gian_bat_dau) if thoi_gian_bat_dau else timezone.now(),
                thoi_gian_ket_thuc=parse_datetime(thoi_gian_ket_thuc) if thoi_gian_ket_thuc else timezone.now(),
                diem_chuan_ngoai_ngu=to_float(request.POST.get('diem_chuan_ngoai_ngu')) or 5.0,
                diem_liet_ngoai_ngu=to_float(request.POST.get('diem_liet_ngoai_ngu')) or 0.0,
                diem_chuan_tin_hoc=to_float(request.POST.get('diem_chuan_tin_hoc')) or 5.0,
                diem_liet_tin_hoc=to_float(request.POST.get('diem_liet_tin_hoc')) or 0.0,
                file_thong_bao=request.FILES.get('file_thong_bao'),
            )
            messages.success(request, f"Tạo thành công đợt thi: {request.POST.get('ten_dot')}")
        except Exception as e:
            messages.error(request, f'Lỗi tạo đợt thi: kiểm tra mã đợt đã tồn tại chưa. ({e})')
        return redirect('students:mofi_dot_thi_list')

    return render(request, 'admin_mofi/pages/dot_thi_list.html', {
        'dot_this': DotThi.objects.all().order_by('-thoi_gian_bat_dau'),
    })


@staff_member_required
def mofi_dot_thi_detail(request, dot_thi_id):
    dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '-ngay_cap_nhat')
    active_tab = request.GET.get('tab', 'tdnn')

    allowed_sorts = {
        'sbd', '-sbd', 'sinh_vien__mssv', '-sinh_vien__mssv',
        'sinh_vien__ho_ten', '-sinh_vien__ho_ten', 'ngay_cap_nhat', '-ngay_cap_nhat',
    }
    if sort_by not in allowed_sorts:
        sort_by = '-ngay_cap_nhat'

    def get_filtered_qs(mon_thi_code):
        qs = LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi=mon_thi_code).select_related('sinh_vien')
        if search_query:
            qs = qs.filter(Q(sinh_vien__mssv__icontains=search_query) | Q(sinh_vien__ho_ten__icontains=search_query))
        if sort_by == 'sbd':
            return qs.annotate(sbd_sort=LPad('sbd', 10, Value('0'))).order_by('sbd_sort')
        if sort_by == '-sbd':
            return qs.annotate(sbd_sort=LPad('sbd', 10, Value('0'))).order_by('-sbd_sort')
        return qs.order_by(sort_by)

    def get_stats(mon_thi_code):
        qs_base = LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi=mon_thi_code)
        total = qs_base.count()
        passed = qs_base.filter(ket_qua_dat=True).count()
        return {
            'total': total,
            'passed': passed,
            'failed': total - passed,
            'rate': round((passed / total * 100), 1) if total else 0,
        }

    return render(request, 'admin_mofi/pages/dot_thi_detail.html', {
        'dot_thi': dot_thi,
        'stats': {
            'tdnn': get_stats('TA_DAU_VAO'),
            'cdr_nn': get_stats('CDR_NGOAI_NGU'),
            'cdr_tin': get_stats('CDR_TIN_HOC'),
        },
        'page_tdnn': Paginator(get_filtered_qs('TA_DAU_VAO'), 50).get_page(request.GET.get('p_tdnn', 1)),
        'page_cdr_nn': Paginator(get_filtered_qs('CDR_NGOAI_NGU'), 50).get_page(request.GET.get('p_cdr_nn', 1)),
        'page_cdr_tin': Paginator(get_filtered_qs('CDR_TIN_HOC'), 50).get_page(request.GET.get('p_cdr_tin', 1)),
        'active_tab': active_tab,
        'search_query': search_query,
        'sort_by': sort_by,
    })


@staff_member_required
def quick_add_diem(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(SinhVien, id=student_id)
        dot_thi = get_object_or_404(DotThi, id=request.POST.get('dot_thi'))
        LichSuThi.objects.create(
            sinh_vien=student,
            dot_thi=dot_thi,
            mon_thi=request.POST.get('mon_thi'),
            diem_thanh_phan_1=to_float(request.POST.get('diem_tp1')),
            diem_thanh_phan_2=to_float(request.POST.get('diem_tp2')),
            diem_thanh_phan_3=to_float(request.POST.get('diem_tp3')),
            diem_thanh_phan_4=to_float(request.POST.get('diem_tp4')),
            diem_tong=to_float(request.POST.get('diem_tong')),
            xep_loai=request.POST.get('xep_loai', '').strip() or None,
            ghi_chu=request.POST.get('ghi_chu', '').strip() or None,
        )
        messages.success(request, 'Đã cập nhật điểm thi.')
    return redirect('students:student_detail', id=student_id)


@staff_member_required
def mofi_sua_diem_thi(request, lich_thi_id):
    lt = get_object_or_404(LichSuThi, id=lich_thi_id)
    if request.method == 'POST':
        lt.diem_thanh_phan_1 = to_float(request.POST.get('diem_thanh_phan_1'))
        lt.diem_thanh_phan_2 = to_float(request.POST.get('diem_thanh_phan_2'))
        lt.diem_thanh_phan_3 = to_float(request.POST.get('diem_thanh_phan_3'))
        lt.diem_thanh_phan_4 = to_float(request.POST.get('diem_thanh_phan_4'))
        lt.diem_tong = to_float(request.POST.get('diem_tong'))
        lt.xep_loai = request.POST.get('xep_loai', '').strip() or lt.xep_loai
        lt.ghi_chu = request.POST.get('ghi_chu', '').strip()
        lt.save()
        messages.success(request, f'Đã cập nhật điểm thành công cho SV: {lt.sinh_vien.mssv}')
        return redirect('students:mofi_dot_thi_detail', dot_thi_id=lt.dot_thi.id)
    return redirect('students:mofi_dot_thi_list')


@staff_member_required
def mofi_export_bang_diem(request, dot_thi_id):
    dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
    qs_export = LichSuThi.objects.filter(dot_thi=dot_thi).select_related('sinh_vien').annotate(
        sbd_sort=LPad('sbd', 10, Value('0'))
    ).order_by('sbd_sort')

    data = []
    for lt in qs_export:
        data.append({
            'MSSV': lt.sinh_vien.mssv,
            'Họ và tên': lt.sinh_vien.ho_ten,
            'Lớp': lt.sinh_vien.lop or '',
            'Môn thi': lt.get_mon_thi_display(),
            'SBD': lt.sbd or '',
            'Ngày thi 1': lt.ngay_thi or '',
            'Ca thi 1': lt.ca_thi or '',
            'Phòng thi 1': lt.phong_thi or '',
            'Ngày thi 2': lt.ngay_thi_2 or '',
            'Ca thi 2': lt.ca_thi_2 or '',
            'Phòng thi 2': lt.phong_thi_2 or '',
            'Điểm TP1': lt.diem_thanh_phan_1 if lt.diem_thanh_phan_1 is not None else '',
            'Điểm TP2': lt.diem_thanh_phan_2 if lt.diem_thanh_phan_2 is not None else '',
            'Điểm TP3': lt.diem_thanh_phan_3 if lt.diem_thanh_phan_3 is not None else '',
            'Điểm TP4': lt.diem_thanh_phan_4 if lt.diem_thanh_phan_4 is not None else '',
            'Điểm tổng': lt.diem_tong if lt.diem_tong is not None else '',
            'Kết quả': 'Đạt' if lt.ket_qua_dat else 'Không đạt',
            'Bảo lưu': 'Có' if lt.co_bao_luu else 'Không',
            'Ghi chú': lt.ghi_chu or '',
        })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(data).to_excel(writer, sheet_name='BangDiem', index=False)
        worksheet = writer.sheets['BangDiem']
        for column_cells in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = max_len + 2

    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    filename = f'bang_diem_{vi_slugify(dot_thi.ma_dot or dot_thi.ten_dot)}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==============================================================================
# 6. IMPORT LỊCH THI & ĐIỂM THI
# ==============================================================================
def import_lich_thi_generic(request, mon_thi_code, template_name, success_label):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        if not dot_thi_id or not excel_file:
            messages.error(request, 'Vui lòng chọn đợt thi và file Excel.')
            return redirect(f'{request.path}?dot={dot_thi_id or ""}')

        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        try:
            visible_sheets = get_visible_sheet_names(excel_file)
            sheets = visible_sheets or [0]
            total_count = 0
            with transaction.atomic():
                LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi=mon_thi_code).delete()
                for sheet in sheets:
                    excel_file.seek(0)
                    df = read_excel_with_smart_header(excel_file, sheet_name=sheet)
                    for _, row in df.iterrows():
                        mssv = extract_mssv(get_first(row, ['mssv', 'ma sinh vien', 'masinhvien', 'ma sv']))
                        if not mssv:
                            continue
                        ho_ten = get_first(row, ['hoten', 'ho ten', 'hovaten', 'ten sinh vien'])
                        lop = get_first(row, ['lop', 'lop sinh hoat'])
                        khoa = get_first(row, ['khoa', 'khoa vien'])
                        sv = ensure_student(mssv, ho_ten=ho_ten, lop=lop, khoa_name=khoa)
                        if not sv:
                            continue

                        LichSuThi.objects.update_or_create(
                            sinh_vien=sv,
                            dot_thi=dot_thi,
                            mon_thi=mon_thi_code,
                            defaults={
                                'sbd': get_first(row, ['sbd', 'so bao danh', 'sobaodanh']),
                                'ngay_thi': get_first(row, ['ngaythi', 'ngay thi', 'ngay thi 1', 'ngaykiemtra']),
                                'ca_thi': get_first(row, ['cathi', 'ca thi', 'ca thi 1', 'kipthi']),
                                'phong_thi': get_first(row, ['phongthi', 'phong thi', 'phong thi 1']),
                                'ngay_thi_2': get_first(row, ['ngaythi2', 'ngay thi 2', 'ngaynoi', 'ngay thi noi']),
                                'ca_thi_2': get_first(row, ['cathi2', 'ca thi 2', 'canoi', 'ca thi noi']),
                                'phong_thi_2': get_first(row, ['phongthi2', 'phong thi 2', 'phongnoi', 'phong thi noi']),
                                'ghi_chu': get_first(row, ['ghichu', 'ghi chu']),
                            },
                        )
                        total_count += 1
            messages.success(request, f'Đã nạp mới {total_count} lịch thi {success_label}.')
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f'Lỗi xử lý file Excel: {e}')
            return redirect(f'{request.path}?dot={dot_thi_id}')

    return render(request, template_name, {'dot_this': DotThi.objects.all().order_by('-id')})


@staff_member_required
def mofi_import_lich_thi_tdnn(request):
    return import_lich_thi_generic(
        request,
        mon_thi_code='TA_DAU_VAO',
        template_name='admin_mofi/pages/import_lich_thi_tdnn.html',
        success_label='Tiếng Anh đầu vào',
    )


@staff_member_required
def mofi_import_lich_thi_nn(request):
    return import_lich_thi_generic(
        request,
        mon_thi_code='CDR_NGOAI_NGU',
        template_name='admin_mofi/pages/import_lich_thi_nn.html',
        success_label='CĐR Ngoại ngữ',
    )


@staff_member_required
def mofi_import_lich_thi_cntt(request):
    return import_lich_thi_generic(
        request,
        mon_thi_code='CDR_TIN_HOC',
        template_name='admin_mofi/pages/import_lich_thi_cntt.html',
        success_label='CĐR Tin học',
    )


def import_diem_generic(request, mon_thi_code, template_name, success_label):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        if not dot_thi_id or not excel_file:
            messages.error(request, 'Vui lòng chọn đợt thi và file Excel.')
            return redirect(f'{request.path}?dot={dot_thi_id or ""}')

        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        try:
            visible_sheets = get_visible_sheet_names(excel_file)
            sheets = visible_sheets or [0]
            total_count = 0

            with transaction.atomic():
                for sheet in sheets:
                    excel_file.seek(0)
                    df = read_excel_with_smart_header(excel_file, sheet_name=sheet)
                    for _, row in df.iterrows():
                        mssv = extract_mssv(get_first(row, ['mssv', 'ma sinh vien', 'masinhvien', 'ma sv']))
                        if not mssv:
                            continue

                        ho_ten = get_first(row, ['hoten', 'ho ten', 'hovaten', 'ten sinh vien'])
                        lop = get_first(row, ['lop', 'lop sinh hoat'])
                        khoa = get_first(row, ['khoa', 'khoa vien'])
                        sv = ensure_student(mssv, ho_ten=ho_ten, lop=lop, khoa_name=khoa)
                        if not sv:
                            continue

                        d1 = get_float_first(row, ['diemtp1', 'tp1', 'nghe', 'tracnghiem', 'lythuyet', 'diem nghe', 'diem tn'])
                        d2 = get_float_first(row, ['diemtp2', 'tp2', 'doc', 'thuchanh', 'diem doc', 'diem th'])
                        d3 = get_float_first(row, ['diemtp3', 'tp3', 'viet', 'diem viet'])
                        d4 = get_float_first(row, ['diemtp4', 'tp4', 'noi', 'diem noi'])
                        diem_tong = get_float_first(row, ['diemtong', 'tongdiem', 'tong', 'diemthi', 'diem'])
                        xep_loai = get_first(row, ['xeploai', 'xep loai', 'ketqua', 'ket qua'])
                        ghi_chu = get_first(row, ['ghichu', 'ghi chu'])

                        bl_parts = []
                        dot_bl = get_first(row, ['dotbaoluu', 'dotbl', 'bao luu dot'])
                        phan_bl = get_first(row, ['phanbaoluu', 'phan bl', 'noi dung bao luu'])
                        if dot_bl:
                            bl_parts.append(f'BL: {dot_bl}')
                        if phan_bl:
                            bl_parts.append(f'Phần: {phan_bl}')
                        co_bao_luu = bool(bl_parts)
                        if co_bao_luu:
                            ghi_chu = ' | '.join(bl_parts + ([ghi_chu] if ghi_chu else []))

                        LichSuThi.objects.update_or_create(
                            sinh_vien=sv,
                            dot_thi=dot_thi,
                            mon_thi=mon_thi_code,
                            defaults={
                                'sbd': get_first(row, ['sbd', 'so bao danh', 'sobaodanh']),
                                'diem_thanh_phan_1': d1,
                                'diem_thanh_phan_2': d2,
                                'diem_thanh_phan_3': d3,
                                'diem_thanh_phan_4': d4,
                                'diem_tong': diem_tong,
                                'xep_loai': xep_loai or None,
                                'ghi_chu': ghi_chu or None,
                                'co_bao_luu': co_bao_luu,
                            },
                        )
                        total_count += 1

            messages.success(request, f'Đã nạp {total_count} bảng điểm {success_label}.')
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f'Lỗi import điểm: {e}')
            return redirect(f'{request.path}?dot={dot_thi_id}')

    return render(request, template_name, {'dot_this': DotThi.objects.all().order_by('-id')})


@staff_member_required
def mofi_import_diem_tdnn(request):
    return import_diem_generic(
        request,
        mon_thi_code='TA_DAU_VAO',
        template_name='admin_mofi/pages/import_diem_tdnn.html',
        success_label='Tiếng Anh đầu vào',
    )


@staff_member_required
def mofi_import_diem_cdr_nn(request):
    return import_diem_generic(
        request,
        mon_thi_code='CDR_NGOAI_NGU',
        template_name='admin_mofi/pages/import_diem_cdr_nn.html',
        success_label='CĐR Ngoại ngữ',
    )


@staff_member_required
def mofi_import_diem_cntt(request):
    return import_diem_generic(
        request,
        mon_thi_code='CDR_TIN_HOC',
        template_name='admin_mofi/pages/import_diem_cntt.html',
        success_label='CĐR Tin học',
    )
