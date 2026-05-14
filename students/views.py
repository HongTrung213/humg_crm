import os
import io
import re
import pandas as pd
from openpyxl import load_workbook
from dateutil.relativedelta import relativedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction, connection, IntegrityError
from django.db.models import Q, Case, When, Value, IntegerField, Count, Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.contrib.auth.models import User, Group, Permission
from django.utils.text import slugify

from .models import SinhVien, LopBoiDuong, DangKyLop, LichSuThi, ChungChi, DotThi, Khoa, DanhMucChungChi
from .forms import DanhMucChungChiForm, UserAccountForm, GroupForm, KhoaForm
from cms.models import Slider, QuickLink, Category, Post
from django.db.models.functions import LPad
from django.db.models import Value

# ==========================================
# SCRIPT DỌN DẸP SLUG (TÙY CHỌN)
# ==========================================
def vi_slugify(text):
    text = text.lower()
    text = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', text)
    text = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', text)
    text = re.sub(r'[ìíịỉĩ]', 'i', text)
    text = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', text)
    text = re.sub(r'[ùúụủũưừứựửữ]', 'u', text)
    text = re.sub(r'[ỳýỵỷỹ]', 'y', text)
    text = re.sub(r'đ', 'd', text)
    return slugify(text)


# ==========================================
# HÀM TIỆN ÍCH LÀM SẠCH VÀ BÓC TÁCH MSSV
# ==========================================
def clean_excel_val(val):
    if pd.isna(val): return ""
    if isinstance(val, float):
        if val.is_integer(): return str(int(val))
    return str(val).strip()

def parse_mssv_humg(mssv):
    """ Tự động nhận diện Khoa dựa trên mã sinh viên HUMG """
    mssv_str = str(mssv).strip()
    if not mssv_str.isdigit() or len(mssv_str) != 10:
        return None
    
    ma_khoa = mssv_str[3:6]
    dict_khoa = {
        '100': 'Khoa Khoa học cơ bản', '101': 'Khoa Dầu khí và Năng lượng',
        '102': 'Khoa Khoa học và Kỹ thuật Địa chất', '103': 'Khoa Trắc địa - Bản đồ và Quản lý đất đai',
        '104': 'Khoa Mỏ', '105': 'Khoa Công nghệ Thông tin',
        '106': 'Khoa Cơ - Điện', '107': 'Khoa Xây dựng', '108': 'Khoa Môi trường',
        '109': 'Chương trình tiên tiến', '401': 'Khoa Kinh tế - Quản trị kinh doanh'
    }
    return dict_khoa.get(ma_khoa, 'Khoa Khác')


# ==========================================
# 1. PHÂN HỆ CÔNG CỘNG (CỔNG THÔNG TIN SINH VIÊN)
# ==========================================
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
    context = {
        'slider_posts': slider_posts, 'quick_links': quick_links,
        'home_blocks': home_blocks, 'latest_posts': latest_posts,
    }
    return render(request, 'students/home.html', context)

def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk, is_published=True)
    related_posts = Post.objects.filter(category=post.category, is_published=True).exclude(pk=pk)[:5]
    return render(request, 'students/post_detail.html', {'post': post, 'related_posts': related_posts})

def tra_cuu(request):
    query_mssv = request.GET.get('mssv', '').strip()
    sinh_vien, lich_thi_sap_toi, ket_qua_thi, thong_bao = None, None, None, None

    if query_mssv:
        try:
            sinh_vien = SinhVien.objects.get(mssv=query_mssv)
            toan_bo_lich_thi = sinh_vien.lich_su_thi.all().order_by('-dot_thi__thoi_gian_bat_dau')
            lich_thi_sap_toi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=True)
            ket_qua_thi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=False)
        except SinhVien.DoesNotExist:
            thong_bao = f"Không tìm thấy dữ liệu cho mã số sinh viên: {query_mssv}"
            
    return render(request, 'students/tra_cuu.html', {
        'sinh_vien': sinh_vien, 'query_mssv': query_mssv, 'thong_bao': thong_bao, 
        'lich_thi_sap_toi': lich_thi_sap_toi, 'ket_qua_thi': ket_qua_thi
    })

def dang_nhap(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('mssv'), password=request.POST.get('password'))
        if user:
            login(request, user)
            messages.success(request, f'Xin chào {user.first_name}!')
            next_url = request.GET.get('next') 
            return redirect(next_url) if next_url else redirect('students:home')
        else:
            messages.error(request, 'Mã sinh viên hoặc mật khẩu không chính xác!')
    return render(request, 'students/login.html')

def dang_xuat(request):
    logout(request)
    messages.info(request, 'Bạn đã đăng xuất thành công.')
    return redirect('students:home')


# ==========================================
# 2. PORTAL SINH VIÊN
# ==========================================
@login_required
def dashboard(request):
    try:
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
        ds_dang_ky = DangKyLop.objects.filter(sinh_vien=sinh_vien).order_by('-thoi_gian_dk')
        khoas = Khoa.objects.all().order_by('ten_khoa')
        danh_muc_cc = DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi')
        sliders = Slider.objects.filter(is_active=True).order_by('order')
        quick_links = QuickLink.objects.filter(is_active=True).order_by('order')

        toan_bo_lich_thi = sinh_vien.lich_su_thi.all().order_by('-dot_thi__thoi_gian_bat_dau')
        lich_thi_sap_toi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=True)
        ket_qua_thi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=False)

        return render(request, 'students/dashboard.html', {
            'sinh_vien': sinh_vien, 'ds_dang_ky': ds_dang_ky, 'khoas': khoas,
            'danh_muc_cc': danh_muc_cc, 'sliders': sliders, 'quick_links': quick_links,
            'lich_thi_sap_toi': lich_thi_sap_toi, 'ket_qua_thi': ket_qua_thi
        })
    except SinhVien.DoesNotExist:
        messages.error(request, "Hồ sơ cá nhân chưa được khởi tạo trên hệ thống.")
        return redirect('students:home')
    
@login_required
def nop_chung_chi(request):
    danh_muc_cc = DanhMucChungChi.objects.all()
    if request.method == 'POST':
        danh_muc_id, so_hieu, ngay_cap = request.POST.get('danh_muc_id'), request.POST.get('so_hieu'), request.POST.get('ngay_cap')
        file_minh_chung = request.FILES.get('file_minh_chung')

        if not danh_muc_id or not so_hieu or not ngay_cap or not file_minh_chung:
            messages.error(request, "Vui lòng điền đầy đủ thông tin và đính kèm file minh chứng!")
            return redirect('students:nop_chung_chi')

        try:
            sinh_vien_hien_tai = SinhVien.objects.get(mssv=request.user.username)
            danh_muc = DanhMucChungChi.objects.get(id=danh_muc_id)
            ChungChi.objects.create(
                sinh_vien=sinh_vien_hien_tai, danh_muc=danh_muc, so_hieu=so_hieu, 
                ngay_cap=ngay_cap, file_minh_chung=file_minh_chung, trang_thai='CHO' 
            )
            messages.success(request, "Tuyệt vời! Đã gửi yêu cầu xét duyệt chứng chỉ thành công.")
        except SinhVien.DoesNotExist:
            messages.error(request, "Tài khoản của bạn chưa được liên kết với hồ sơ Sinh viên!")
        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra: {str(e)}")
        return redirect('students:nop_chung_chi')
    return render(request, 'students/nop_chung_chi.html', {'danh_muc_cc': danh_muc_cc})

@login_required
def quick_add_cert_portal(request):
    if request.method == 'POST':
        try:
            sinh_vien = SinhVien.objects.get(mssv=request.user.username)
            danh_muc = get_object_or_404(DanhMucChungChi, id=request.POST.get('danh_muc_id'))
            ChungChi.objects.create(
                sinh_vien=sinh_vien, danh_muc=danh_muc, so_hieu=request.POST.get('so_hieu'), 
                ngay_cap=request.POST.get('ngay_cap'), file_minh_chung=request.FILES.get('file_minh_chung'), trang_thai='CHO'
            )
            messages.success(request, 'Đã gửi hồ sơ chứng chỉ thành công!')
        except Exception as e:
            messages.error(request, f'Lỗi nộp hồ sơ: {e}')
    return redirect('students:dashboard')

@login_required
def student_delete_cert(request, cert_id):
    cert = get_object_or_404(ChungChi, id=cert_id, sinh_vien__mssv=request.user.username)
    if cert.trang_thai == 'CHO':
        if cert.file_minh_chung: cert.file_minh_chung.delete()
        cert.delete()
        messages.success(request, "Đã hủy hồ sơ thành công.")
    else:
        messages.error(request, "Hồ sơ đã được xử lý, không thể tự xóa.")
    return redirect('students:dashboard')

@login_required
def cap_nhat_ho_so(request):
    if request.method == 'POST':
        try:
            sinh_vien = SinhVien.objects.get(mssv=request.user.username)
            if request.POST.get('so_dien_thoai'): sinh_vien.so_dien_thoai = request.POST.get('so_dien_thoai')
            if request.POST.get('email_ca_nhan'): sinh_vien.email_ca_nhan = request.POST.get('email_ca_nhan')
            if request.FILES.get('anh_dai_dien'): sinh_vien.anh_dai_dien = request.FILES.get('anh_dai_dien')
            sinh_vien.save()
            messages.success(request, 'Cập nhật thông tin thành công!')
        except SinhVien.DoesNotExist:
            messages.error(request, 'Lỗi hồ sơ.')
    return redirect('students:dashboard')

@login_required
def danh_sach_lop(request):
    try: sinh_vien = SinhVien.objects.get(mssv=request.user.username)
    except SinhVien.DoesNotExist: return redirect('students:home')

    if request.method == 'POST':
        lop_id, file_mc = request.POST.get('lop_id'), request.FILES.get('file_minh_chung')
        if not file_mc:
            messages.error(request, 'Vui lòng đính kèm biên lai.')
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
    return render(request, 'students/danh_sach_lop.html', {'lops': lops, 'da_dang_ky_ids': da_dang_ky_ids, 'sinh_vien': sinh_vien})

def quy_che(request): return render(request, 'students/quy_che.html')
def lich_thi(request): return render(request, 'students/lich_thi.html')


# ==========================================
# 3. QUẢN TRỊ ADMIN (DASHBOARD & HỒ SƠ)
# ==========================================
@login_required
def admin_mofi_dashboard(request):
    if not request.user.is_staff: return redirect('students:home')
    
    # Lấy toàn bộ sinh viên, lọc ra sinh viên từ Năm 4 (Cảnh báo sớm)
    tat_ca_sv = SinhVien.objects.select_related('khoa').all()
    sv_canh_bao_nam_cuoi = [sv for sv in tat_ca_sv if getattr(sv, 'tien_do_nam_tu', False)]
    
    thong_ke_khoa = {}
    danh_sach_chua_dat = []

    # Thống kê theo Khoa (Dành riêng cho sinh viên năm 4 trở lên)
    for sv in sv_canh_bao_nam_cuoi:
        ten_khoa = sv.khoa.ten_khoa if sv.khoa else "Chưa phân khoa"
        if ten_khoa not in thong_ke_khoa:
            thong_ke_khoa[ten_khoa] = {'tong': 0, 'dat': 0, 'chua_dat': 0}
            
        thong_ke_khoa[ten_khoa]['tong'] += 1
        
        if getattr(sv, 'chua_dat_chuan_dau_ra', False):
            thong_ke_khoa[ten_khoa]['chua_dat'] += 1
            danh_sach_chua_dat.append(sv) # Báo động đỏ
        else:
            thong_ke_khoa[ten_khoa]['dat'] += 1

    # Sắp xếp
    list_thong_ke_khoa = [{'ten_khoa': k, **v} for k, v in thong_ke_khoa.items()]
    list_thong_ke_khoa.sort(key=lambda x: x['tong'], reverse=True)
    danh_sach_chua_dat.sort(key=lambda x: getattr(x, 'nam_nhap_hoc', 9999) or 9999)

    context = {
        'total_students': tat_ca_sv.count(),
        'active_classes': LopBoiDuong.objects.filter(trang_thai=True).count(),
        'pending_registrations': DangKyLop.objects.filter(trang_thai='CHO_DUYET').count(),
        'certificates_issued': ChungChi.objects.count(),
        'recent_activities': DangKyLop.objects.select_related('sinh_vien', 'lop_hoc').order_by('-thoi_gian_dk')[:5],
        
        'thong_ke_khoa': list_thong_ke_khoa,
        'so_luong_canh_bao': len(danh_sach_chua_dat),
        'top_canh_bao': danh_sach_chua_dat[:10],
    }
    return render(request, 'admin_mofi/pages/dashboard.html', context)

@login_required
def student_list(request):
    if not request.user.is_staff: return redirect('students:home')
    sinhviens = SinhVien.objects.select_related('khoa').all().order_by('-mssv')
    return render(request, 'admin_mofi/students/student_list.html', {'sinhviens': sinhviens})

@login_required
def student_detail(request, id):
    if not request.user.is_staff: return redirect('students:home')
    student = get_object_or_404(SinhVien, id=id)
    danh_muc_cc = DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi')
    return render(request, 'admin_mofi/students/student_detail.html', {
        'student': student, 'ds_dang_ky': student.ds_dang_ky_lop.all().order_by('-thoi_gian_dk'), 
        'lich_su_thi': student.lich_su_thi.all().order_by('-ngay_cap_nhat'), 'danh_muc_cc': danh_muc_cc
    })

@login_required
def student_add(request):
    if not request.user.is_staff: return redirect('students:home')
    if request.method == 'POST':
        SinhVien.objects.create(
            mssv=request.POST.get('mssv', '').strip(), ho_ten=request.POST.get('ho_ten'),
            khoa_id=request.POST.get('khoa'), lop=request.POST.get('lop'),
            so_dien_thoai=request.POST.get('so_dien_thoai'), email_ca_nhan=request.POST.get('email_ca_nhan'),
            anh_dai_dien=request.FILES.get('anh_dai_dien')
        )
        messages.success(request, "Thêm sinh viên thành công!")
        return redirect('students:student_list')
    return render(request, 'admin_mofi/students/student_form.html', {'khoas': Khoa.objects.all(), 'danh_muc_cc': DanhMucChungChi.objects.all()})

@login_required
def student_edit(request, id):
    if not request.user.is_staff: return redirect('students:home')
    student = get_object_or_404(SinhVien, id=id)
    if request.method == 'POST':
        student.khoa_id, student.ho_ten, student.lop = request.POST.get('khoa'), request.POST.get('ho_ten'), request.POST.get('lop')
        student.so_dien_thoai, student.email_ca_nhan = request.POST.get('so_dien_thoai'), request.POST.get('email_ca_nhan')
        if request.FILES.get('anh_dai_dien'): student.anh_dai_dien = request.FILES.get('anh_dai_dien')
        student.save()
        messages.success(request, "Cập nhật thành công!")
        return redirect('students:student_list')
    return render(request, 'admin_mofi/students/student_form.html', {'student': student, 'khoas': Khoa.objects.all(), 'danh_muc_cc': DanhMucChungChi.objects.all()})

@login_required
def student_delete(request, id):
    if not request.user.is_staff: return redirect('students:home')
    student = get_object_or_404(SinhVien, id=id)
    ten_sv = student.ho_ten
    student.delete() 
    messages.success(request, f"Đã xóa hồ sơ của: {ten_sv}")
    return redirect('students:student_list')

@login_required
def import_sinh_vien(request):
    if not request.user.is_staff: return redirect('students:home')
    if request.method == 'POST':
        try:
            df = pd.read_excel(request.FILES.get('excel_file'))
            for _, row in df.dropna(subset=['MSSV']).iterrows():
                khoa_str = str(row.get('Khoa', '')).strip()
                khoa_obj, _ = Khoa.objects.get_or_create(ten_khoa=khoa_str) if khoa_str and khoa_str.lower() != 'nan' else (None, False)
                SinhVien.objects.update_or_create(
                    mssv=str(row['MSSV']).strip(),
                    defaults={'ho_ten': str(row.get('HoTen', '')).strip(), 'khoa': khoa_obj}
                )
            messages.success(request, "Nhập dữ liệu thành công!")
            return redirect('students:student_list')
        except Exception as e:
            messages.error(request, f"Lỗi: {e}")
    return render(request, 'admin_mofi/students/import_excel.html')


# ==========================================
# 4. QUẢN LÝ LỚP HỌC & CHỨNG CHỈ
# ==========================================
@login_required
def class_list(request):
    if not request.user.is_staff: return redirect('students:home')
    return render(request, 'admin_mofi/pages/class_list.html', {'classes': LopBoiDuong.objects.all().order_by('-id')}) 

@login_required
def registration_list(request):
    if not request.user.is_staff: return redirect('students:home')
    regs = DangKyLop.objects.all().order_by(Case(When(trang_thai='CHO_DUYET', then=Value(0)), default=Value(1), output_field=IntegerField()), '-thoi_gian_dk')
    return render(request, 'admin_mofi/classes/registration_list.html', {'registrations': regs})

@login_required
def approve_registration(request, id):
    if not request.user.is_staff: return redirect('students:home')
    reg = get_object_or_404(DangKyLop, id=id)
    if request.method == 'POST':
        reg.trang_thai = 'THANH_CONG' if request.POST.get('action') == 'approve' else 'DA_HUY'
        reg.save()
        messages.success(request, "Xử lý thành công.")
    return redirect('students:registration_list')

@staff_member_required
def mofi_import_class_list(request):
    if request.method == 'POST':
        lop_id, excel_file = request.POST.get('lop_id'), request.FILES.get('excel_file')
        if not excel_file or not lop_id:
            messages.error(request, "Vui lòng chọn lớp học và file Excel.")
            return redirect('students:mofi_import_class_list')
            
        lop_hoc = get_object_or_404(LopBoiDuong, id=lop_id)
        try:
            df_raw = pd.read_excel(excel_file, header=None)
            header_row = next((i for i, row in df_raw.iterrows() if any('mã sinh viên' in str(v).lower() for v in row.values)), 0)
            df = pd.read_excel(excel_file, header=header_row)
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            count = 0
            for _, row in df.iterrows():
                mssv_key = next((c for c in df.columns if 'mã' in c and 'sinh viên' in c or 'mssv' in c), None)
                if not mssv_key or pd.isna(row[mssv_key]): continue
                mssv = str(row[mssv_key]).split('.')[0].strip()
                try:
                    sv = SinhVien.objects.get(mssv=mssv)
                    DangKyLop.objects.update_or_create(sinh_vien=sv, lop_hoc=lop_hoc, defaults={'trang_thai': 'THANH_CONG'})
                    count += 1
                except SinhVien.DoesNotExist: continue
            
            messages.success(request, f"Đã thêm thành công {count} sinh viên vào lớp {lop_hoc.ten_lop}!")
            return redirect('students:class_list')
        except Exception as e:
            messages.error(request, f"Lỗi xử lý file Excel: {str(e)}")
            
    return render(request, 'admin_mofi/pages/import_class_list.html', {'lops': LopBoiDuong.objects.filter(trang_thai=True).order_by('-id')})

@login_required
def quick_add_chung_chi(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(SinhVien, id=student_id)
        danh_muc = get_object_or_404(DanhMucChungChi, id=request.POST.get('danh_muc_id'))
        so_hieu_nhap = request.POST.get('so_hieu').strip()
        try:
            ChungChi.objects.create(
                sinh_vien=student, danh_muc=danh_muc, so_hieu=so_hieu_nhap, ngay_cap=request.POST.get('ngay_cap'),
                file_minh_chung=request.FILES.get('file_minh_chung'), trang_thai='CHO'
            )
            messages.success(request, "Đã tải lên chứng chỉ mới thành công.")
        except IntegrityError:
            messages.error(request, f"Từ chối: Chứng chỉ mang số hiệu '{so_hieu_nhap}' đã tồn tại trong hồ sơ của sinh viên này!")
    return redirect('students:student_detail', id=student_id)

@login_required
def certificate_verification_list(request):
    if not request.user.is_staff: return redirect('students:home')
    pending_certs = ChungChi.objects.filter(trang_thai='CHO').select_related('sinh_vien', 'danh_muc').order_by('ngay_cap')
    return render(request, 'admin_mofi/certificates/cert_list.html', {'pending_certs': pending_certs})

@login_required
def verify_certificate(request, cert_id):
    if not request.user.is_staff: return redirect('students:home')
    cert = get_object_or_404(ChungChi, id=cert_id)
    if request.method == 'POST':
        action, ghi_chu = request.POST.get('action'), request.POST.get('ghi_chu', '').strip()
        if action == 'approve':
            cert.trang_thai, cert.ghi_chu_xac_minh = 'DAT', ghi_chu or "Chứng chỉ hợp lệ."
            messages.success(request, f"Đã duyệt cho {cert.sinh_vien.ho_ten}")
        elif action == 'reject':
            cert.trang_thai, cert.ghi_chu_xac_minh = 'KHONG_DAT', ghi_chu or "Thông tin chưa chính xác."
            messages.warning(request, f"Đã báo lỗi hồ sơ của {cert.sinh_vien.ho_ten}")
        elif action == 'delete':
            ten_sv = cert.sinh_vien.ho_ten
            if cert.file_minh_chung: cert.file_minh_chung.delete()
            cert.delete()
            messages.error(request, f"Đã xóa file rác của {ten_sv}.")
            return redirect(request.META.get('HTTP_REFERER', 'certificate_verification_list'))
        cert.save()
    return redirect(request.META.get('HTTP_REFERER', 'certificate_verification_list'))

@login_required
def delete_certificate(request, cert_id):
    if not request.user.is_staff: return redirect('students:home')
    cert = get_object_or_404(ChungChi, id=cert_id)
    ten_sv = cert.sinh_vien.ho_ten
    if cert.file_minh_chung: cert.file_minh_chung.delete()
    cert.delete()
    messages.success(request, f"Đã xóa chứng chỉ của {ten_sv}.")
    return redirect(request.META.get('HTTP_REFERER', 'certificate_verification_list'))


# ==========================================
# 5. QUẢN LÝ MASTER DATA (TÀI KHOẢN, KHOA, DANH MỤC)
# ==========================================
@staff_member_required
def mofi_khoa_list(request):
    query = request.GET.get('q', '')
    danh_sach_khoa = Khoa.objects.all().order_by('ten_khoa')
    if query: danh_sach_khoa = danh_sach_khoa.filter(ten_khoa__icontains=query)
    return render(request, 'admin_mofi/pages/khoa_list.html', {'danh_sach_khoa': danh_sach_khoa, 'query': query})

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
def mofi_chungchi_list(request):
    query = request.GET.get('q', '')
    danh_sach = DanhMucChungChi.objects.all().order_by('-id')
    if query: danh_sach = danh_sach.filter(Q(ten_chung_chi__icontains=query) | Q(loai__icontains=query))
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
    users = User.objects.all().order_by('-date_joined')
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
    if user.is_superuser: messages.error(request, 'Cảnh báo: Không thể xóa tài khoản SuperAdmin tối cao!')
    else:
        user.delete()
        messages.success(request, 'Đã xóa tài khoản Cán bộ thành công.')
    return redirect('students:mofi_user_list')

@staff_member_required
def mofi_group_list(request):
    return render(request, 'admin_mofi/system/group_list.html', {'groups': Group.objects.all()})

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


# ==========================================
# 6. QUẢN LÝ ĐỢT THI & CẤU HÌNH (LÕI HỆ THỐNG)
# ==========================================
@staff_member_required
def mofi_dot_thi_list(request):
    if request.method == 'POST':
        try:
            thoi_gian_bat_dau = request.POST.get('thoi_gian_bat_dau')
            thoi_gian_ket_thuc = request.POST.get('thoi_gian_ket_thuc')
            DotThi.objects.create(
                ma_dot=request.POST.get('ma_dot'), ten_dot=request.POST.get('ten_dot'),
                thoi_gian_bat_dau=parse_datetime(thoi_gian_bat_dau) if thoi_gian_bat_dau else timezone.now(),
                thoi_gian_ket_thuc=parse_datetime(thoi_gian_ket_thuc) if thoi_gian_ket_thuc else timezone.now(),
                diem_chuan_ngoai_ngu=float(request.POST.get('diem_chuan_ngoai_ngu', 5.0)),
                diem_liet_ngoai_ngu=float(request.POST.get('diem_liet_ngoai_ngu', 0.0)),
                diem_chuan_tin_hoc=float(request.POST.get('diem_chuan_tin_hoc', 5.0)),
                diem_liet_tin_hoc=float(request.POST.get('diem_liet_tin_hoc', 0.0)),
                file_thong_bao=request.FILES.get('file_thong_bao'),
            )
            messages.success(request, f"Tạo thành công đợt thi: {request.POST.get('ten_dot')}")
        except Exception as e:
            messages.error(request, f"Lỗi tạo đợt thi: Kiểm tra xem Mã đợt đã tồn tại chưa. ({str(e)})")
        return redirect('students:mofi_dot_thi_list')

    return render(request, 'admin_mofi/pages/dot_thi_list.html', {'dot_this': DotThi.objects.all().order_by('-thoi_gian_bat_dau')})

@staff_member_required
def mofi_dot_thi_detail(request, dot_thi_id):
    dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '-ngay_cap_nhat')
    active_tab = request.GET.get('tab', 'tdnn')

    def get_filtered_qs(mon_thi_code):
        qs = LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi=mon_thi_code).select_related('sinh_vien')
        
        # Lọc theo ô tìm kiếm
        if search_query: 
            qs = qs.filter(Q(sinh_vien__mssv__icontains=search_query) | Q(sinh_vien__ho_ten__icontains=search_query))
            
        # SẮP XẾP SỐ BÁO DANH THÔNG MINH
        if sort_by == 'sbd':
            # Padding 10 số 0 vào trước SBD để sort chuỗi giống sort số
            qs = qs.annotate(sbd_sort=LPad('sbd', 10, Value('0'))).order_by('sbd_sort')
        elif sort_by == '-sbd':
            qs = qs.annotate(sbd_sort=LPad('sbd', 10, Value('0'))).order_by('-sbd_sort')
        else:
            qs = qs.order_by(sort_by)
            
        return qs
    
    def get_stats(mon_thi_code):
        qs_base = LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi=mon_thi_code)
        total, passed = qs_base.count(), qs_base.filter(ket_qua_dat=True).count()
        return {'total': total, 'passed': passed, 'failed': total - passed, 'rate': round((passed / total * 100), 1) if total > 0 else 0}

    stats = {'tdnn': get_stats('TA_DAU_VAO'), 'cdr_nn': get_stats('CDR_NGOAI_NGU'), 'cdr_tin': get_stats('CDR_TIN_HOC')}
    
    page_tdnn = Paginator(get_filtered_qs('TA_DAU_VAO'), 50).get_page(request.GET.get('p_tdnn', 1))
    page_cdr_nn = Paginator(get_filtered_qs('CDR_NGOAI_NGU'), 50).get_page(request.GET.get('p_cdr_nn', 1))
    page_cdr_tin = Paginator(get_filtered_qs('CDR_TIN_HOC'), 50).get_page(request.GET.get('p_cdr_tin', 1))

    context = {
        'dot_thi': dot_thi, 'stats': stats, 'page_tdnn': page_tdnn, 'page_cdr_nn': page_cdr_nn, 'page_cdr_tin': page_cdr_tin,
        'active_tab': active_tab, 'search_query': search_query, 'sort_by': sort_by
    }
    return render(request, 'admin_mofi/pages/dot_thi_detail.html', context)

@login_required
def quick_add_diem(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(SinhVien, id=student_id)
        LichSuThi.objects.create(
            sinh_vien=student, dot_thi_id=request.POST.get('dot_thi'), mon_thi=request.POST.get('mon_thi'),
            diem_thanh_phan_1=request.POST.get('diem_tp1') or None, diem_thanh_phan_2=request.POST.get('diem_tp2') or None
        )
        messages.success(request, "Đã cập nhật điểm thi.")
    return redirect('students:student_detail', id=student_id) 

@staff_member_required
def mofi_sua_diem_thi(request, lich_thi_id):
    if request.method == 'POST':
        lt = get_object_or_404(LichSuThi, id=lich_thi_id)
        diem1, diem2 = request.POST.get('diem_thanh_phan_1'), request.POST.get('diem_thanh_phan_2')
        if diem1: lt.diem_thanh_phan_1 = float(diem1)
        if diem2: lt.diem_thanh_phan_2 = float(diem2)
        lt.ghi_chu = request.POST.get('ghi_chu', '').strip()
        lt.save()
        messages.success(request, f"Đã cập nhật điểm thành công cho SV: {lt.sinh_vien.mssv}")
        return redirect('students:mofi_dot_thi_detail', dot_thi_id=lt.dot_thi.id)
    return redirect('students:mofi_dot_thi_list')

@staff_member_required
def mofi_export_bang_diem(request, dot_thi_id):
    dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
    data = []
    # Dùng LPad để xuất Excel cũng sắp xếp chuẩn 1-2-3-4
    qs_export = LichSuThi.objects.filter(dot_thi=dot_thi).select_related('sinh_vien').annotate(
        sbd_sort=LPad('sbd', 10, Value('0'))
    ).order_by('sbd_sort')

    for lt in qs_export:
        data.append({
            'MSSV': lt.sinh_vien.mssv, 'Họ và tên': lt.sinh_vien.ho_ten, 'Lớp': lt.sinh_vien.lop or '',
            'Ca thi': lt.ca_thi or '', 'Phòng thi': lt.phong_thi or '', 'SBD': lt.sbd or '',
            'Điểm TP1': lt.diem_thanh_phan_1 if lt.diem_thanh_phan_1 is not None else '',
            'Điểm TP2': lt.diem_thanh_phan_2 if lt.diem_thanh_phan_2 is not None else '',
            'Ghi chú': lt.ghi_chu or ''
        })
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(data).to_excel(writer, sheet_name='BangDiem', index=False)
        worksheet = writer.sheets['BangDiem']
        for column_cells in worksheet.columns:
            worksheet.column_dimensions[column_cells[0].column_letter].width = max(len(str(cell.value)) for cell in column_cells) + 2

    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Bang_Diem_{str(dot_thi.ten_dot).replace(" ", "_")}.xlsx"'
    return response


# ==========================================
# 7. IMPORT BẰNG EXCEL (LỊCH THI & ĐIỂM SỐ)
# ==========================================
@staff_member_required
def mofi_import_lich_thi_cntt(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và tải lên file.")
            return redirect('students:mofi_dot_thi_list')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            wb = load_workbook(excel_file, read_only=True)
            visible_sheets = [s.title for s in wb.worksheets if s.sheet_state == 'visible']
            wb.close()
            excel_file.seek(0)
            sheets_dict = pd.read_excel(excel_file, sheet_name=visible_sheets, header=None)
            
            def clean_col(text):
                if pd.isna(text): return ""
                text = str(text).lower()
                for a, b in zip('àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ', 
                                'aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd'):
                    text = text.replace(a, b)
                return re.sub(r'[^a-z0-9]', '', text)

            total_count = 0
            # Xóa lịch cũ của đợt này để nạp mới
            LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi='CDR_TIN_HOC').delete()

            for sheet_name, df_raw in sheets_dict.items():
                col_map = {'ngay': [], 'ca': [], 'phong': []}
                for i in range(min(15, len(df_raw))):
                    for j, val in enumerate(df_raw.iloc[i].values):
                        if pd.isna(val) or len(str(val)) > 100: continue
                        v = clean_col(val)
                        if v in ['msv', 'masinhvien', 'mssv']: col_map['mssv'] = j
                        elif v in ['stt', 'sothutu']: col_map['stt'] = j
                        elif v in ['hodem', 'ho', 'hovatendem']: col_map['ho'] = j
                        elif v == 'ten': col_map['ten'] = j
                        elif 'ngay' in v: col_map['ngay'].append(j)
                        elif 'ca' in v: col_map['ca'].append(j)
                        elif 'phong' in v: col_map['phong'].append(j)
                
                if 'mssv' not in col_map: continue
                
                start_row = None
                for i in range(len(df_raw)):
                    val_mssv = re.sub(r'\D', '', str(df_raw.iloc[i, col_map['mssv']]))
                    if val_mssv.isdigit() and len(val_mssv) >= 5:
                        start_row = i
                        break
                if start_row is None: continue

                for i in range(start_row, len(df_raw)):
                    row = df_raw.iloc[i]
                    mssv = re.sub(r'\D', '', str(row.iloc[col_map['mssv']]).split('.')[0])
                    if not mssv or len(mssv) < 5: continue
                    
                    ho = str(row.iloc[col_map['ho']]).strip() if 'ho' in col_map else ""
                    ten = str(row.iloc[col_map['ten']]).strip() if 'ten' in col_map else ""
                    ho_ten = f"{ho} {ten}".strip() or f"SV_{mssv}"

                    with transaction.atomic():
                        user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                        if _: user.set_password('cfihumg'); user.save()
                        
                        # --- TỰ ĐỘNG GÁN KHOA KHI TẠO SV ---
                        ten_k = parse_mssv_humg(mssv)
                        def_sv = {'user': user, 'ho_ten': ho_ten}
                        if ten_k:
                            k_obj, _ = Khoa.objects.get_or_create(ten_khoa=ten_k)
                            def_sv['khoa'] = k_obj

                        sv, sv_c = SinhVien.objects.get_or_create(mssv=mssv, defaults=def_sv)
                        if not sv_c and not sv.khoa and ten_k:
                            sv.khoa = k_obj; sv.save()

                        def gv(lst, pos):
                            if len(lst) > pos and pd.notna(row.iloc[lst[pos]]):
                                return str(row.iloc[lst[pos]]).strip()
                            return ""

                        LichSuThi.objects.create(
                            sinh_vien=sv, dot_thi=dot_thi, mon_thi='CDR_TIN_HOC',
                            sbd=gv([col_map['stt']], 0) if 'stt' in col_map else "",
                            ngay_thi=gv(col_map['ngay'], 0), ca_thi=gv(col_map['ca'], 0), phong_thi=gv(col_map['phong'], 0)
                        )
                    total_count += 1
            messages.success(request, f"✅ Đã nạp {total_count} lịch thi CNTT.")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f"❌ Lỗi: {e}")
            return redirect('students:mofi_dot_thi_list')
    return render(request, 'admin_mofi/pages/import_lich_thi_cntt.html', {'dot_this': DotThi.objects.all().order_by('-id')})

@staff_member_required
def mofi_import_diem_cntt(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            excel_file.seek(0)
            df_raw = pd.read_excel(excel_file, header=None)
            
            header_idx = None
            for i, row in df_raw.iterrows():
                row_str = "".join([str(v).lower() for v in row.values if pd.notna(v)])
                if 'mssv' in row_str or 'masinhvien' in row_str:
                    header_idx = i; break
            if header_idx is None: raise Exception("Không tìm thấy dòng tiêu đề cột.")

            df_data = df_raw.iloc[header_idx+1:].copy()
            df_data.columns = [vi_slugify(str(c)).replace('-', '') for c in df_raw.iloc[header_idx]]
            
            total_count = 0
            with transaction.atomic():
                for _, row in df_data.iterrows():
                    mssv_raw = str(row.get('mssv', row.get('masinhvien', '')))
                    mssv = re.sub(r'\D', '', mssv_raw.split('.')[0])
                    if not mssv or len(mssv) < 5: continue

                    # --- NHẬN DIỆN KÝ TỰ BẢO LƯU ---
                    is_bl = False; bl_txt = []
                    d_bl = row.get('dotbaoluu', row.get('dotbl', ''))
                    p_bl = row.get('phanbaoluu', '')
                    if pd.notna(d_bl) and str(d_bl).strip(): is_bl = True; bl_txt.append(f"BL: {d_bl}")
                    if pd.notna(p_bl) and str(p_bl).strip(): is_bl = True; bl_txt.append(f"Phần: {p_bl}")

                    user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                    if _: user.set_password('cfihumg'); user.save()
                    
                    ten_k = parse_mssv_humg(mssv)
                    sv, sv_c = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': f"SV_{mssv}"})
                    if (sv_c or not sv.khoa) and ten_k:
                        sv.khoa, _ = Khoa.objects.get_or_create(ten_khoa=ten_k); sv.save()

                    LichSuThi.objects.update_or_create(
                        sinh_vien=sv, dot_thi=dot_thi, mon_thi='CDR_TIN_HOC',
                        defaults={
                            'diem_thanh_phan_1': pd.to_numeric(row.get('tracnghiem', row.get('lythuyet')), errors='coerce'),
                            'diem_thanh_phan_2': pd.to_numeric(row.get('thuchanh')),
                            'co_bao_luu': is_bl,
                            'ghi_chu': " | ".join(bl_txt) if is_bl else row.get('ghichu', '')
                        }
                    )
                    total_count += 1
            messages.success(request, f"✅ Đã nạp {total_count} bảng điểm CNTT.")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f"❌ Lỗi: {e}")
            return redirect('students:mofi_import_diem_cntt')
    return render(request, 'admin_mofi/pages/import_diem_cntt.html', {'dot_this': DotThi.objects.all().order_by('-id')})

@staff_member_required
def mofi_import_lich_thi_nn(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và file.")
            return redirect(f"{reverse('students:mofi_import_lich_thi_nn')}?dot={dot_thi_id}")
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            wb = load_workbook(excel_file, read_only=True)
            visible_sheets = [s.title for s in wb.worksheets if s.sheet_state == 'visible']
            wb.close()
            excel_file.seek(0)
            sheets_dict = pd.read_excel(excel_file, sheet_name=visible_sheets, header=None)
            
            def clean_name(t):
                if pd.isna(t): return ""
                t = str(t).lower()
                for a, b in zip('àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ', 
                                'aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd'):
                    t = t.replace(a, b)
                return re.sub(r'[^a-z0-9]', '', t)

            total_count = 0
            LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi='CDR_NGOAI_NGU').delete()

            for sheet_name, df_raw in sheets_dict.items():
                col_map = {'ngay': [], 'ca': [], 'phong': []}
                for i in range(min(15, len(df_raw))):
                    for j, val in enumerate(df_raw.iloc[i].values):
                        if pd.isna(val) or len(str(val)) > 100: continue
                        v = clean_name(val)
                        if v in ['msv', 'masinhvien', 'mssv']: col_map['mssv'] = j
                        elif v in ['stt', 'sothutu']: col_map['stt'] = j 
                        elif v in ['hodem', 'ho', 'hovatendem']: col_map['ho'] = j
                        elif v == 'ten': col_map['ten'] = j
                        elif 'ngaykt' in v or 'ngaythi' in v or v == 'ngay': 
                            if j not in col_map['ngay']: col_map['ngay'].append(j)
                        elif 'cakt' in v or 'cathi' in v or v == 'ca': 
                            if j not in col_map['ca']: col_map['ca'].append(j)
                        elif 'phongthi' in v or 'phong' in v: 
                            if j not in col_map['phong']: col_map['phong'].append(j)
                
                if 'mssv' not in col_map: continue
                
                start_row = None
                for i in range(len(df_raw)):
                    val = str(df_raw.iloc[i, col_map['mssv']]).split('.')[0].strip()
                    if re.sub(r'\D', '', val).isdigit() and len(re.sub(r'\D', '', val)) >= 5:
                        start_row = i
                        break
                if start_row is None: continue

                for i in range(start_row, len(df_raw)):
                    row = df_raw.iloc[i]
                    mssv = re.sub(r'\D', '', str(row.iloc[col_map['mssv']]).split('.')[0].strip())
                    if not mssv or len(mssv) < 5: continue
                    
                    ho = str(row.iloc[col_map['ho']]).strip() if 'ho' in col_map and pd.notna(row.iloc[col_map['ho']]) else ""
                    ten = str(row.iloc[col_map['ten']]).strip() if 'ten' in col_map and pd.notna(row.iloc[col_map['ten']]) else ""
                    full_name = f"{ho} {ten}".strip()
                    stt_val = str(row.iloc[col_map['stt']]).split('.')[0].strip() if 'stt' in col_map else ""

                    with transaction.atomic():
                        user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                        if _: user.set_password('cfihumg'); user.save()
                        
                        ten_khoa = parse_mssv_humg(mssv)
                        defaults_sv = {'user': user, 'ho_ten': full_name}
                        if ten_khoa:
                            khoa_obj, _ = Khoa.objects.get_or_create(ten_khoa=ten_khoa)
                            defaults_sv['khoa'] = khoa_obj

                        sv, sv_created = SinhVien.objects.get_or_create(mssv=mssv, defaults=defaults_sv)
                        
                        if not sv_created:
                            need_save = False
                            if sv.ho_ten != full_name and len(full_name) > len(sv.ho_ten):
                                sv.ho_ten = full_name
                                need_save = True
                            if not sv.khoa and ten_khoa:
                                khoa_obj, _ = Khoa.objects.get_or_create(ten_khoa=ten_khoa)
                                sv.khoa = khoa_obj
                                need_save = True
                            if need_save: sv.save()

                        def gv(lst, pos):
                            if len(lst) > pos and pd.notna(row.iloc[lst[pos]]):
                                val = str(row.iloc[lst[pos]]).strip()
                                return val if val.lower() != 'nan' else ""
                            return ""

                        LichSuThi.objects.update_or_create(
                            sinh_vien=sv, dot_thi=dot_thi, mon_thi='CDR_NGOAI_NGU',
                            defaults={
                                'sbd': stt_val, 
                                'ngay_thi': gv(col_map['ngay'], 0), 'ca_thi': gv(col_map['ca'], 0), 'phong_thi': gv(col_map['phong'], 0),
                                'ngay_thi_2': gv(col_map['ngay'], 1), 'ca_thi_2': gv(col_map['ca'], 1), 'phong_thi_2': gv(col_map['phong'], 1),
                            }
                        )
                    total_count += 1

            messages.success(request, f"✅ Đã dọn rác và nạp mới {total_count} sinh viên Ngoại ngữ thành công!")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f"❌ Lỗi xử lý file Excel: {str(e)}")
            return redirect(f"{reverse('students:mofi_import_lich_thi_nn')}?dot={dot_thi_id}")
    return render(request, 'admin_mofi/pages/import_lich_thi_nn.html', {'dot_this': DotThi.objects.all().order_by('-id')})

@staff_member_required
def mofi_import_diem_cdr_nn(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        try:
            df_raw = pd.read_excel(excel_file, header=None)
            header_idx = None
            for i, row in df_raw.iterrows():
                r_str = "".join([str(v).lower() for v in row.values if pd.notna(v)])
                if 'mssv' in r_str or 'masinhvien' in r_str: header_idx = i; break
            
            df_data = df_raw.iloc[header_idx+1:].copy()
            df_data.columns = [vi_slugify(str(c)).replace('-', '') for c in df_raw.iloc[header_idx]]
            
            count = 0
            with transaction.atomic():
                for _, row in df_data.iterrows():
                    mssv = re.sub(r'\D', '', str(row.get('mssv', row.get('masinhvien', ''))).split('.')[0])
                    if not mssv or len(mssv) < 5: continue

                    is_bl = False; bl_txt = []
                    d_bl = row.get('dotbaoluu', row.get('dotbl', ''))
                    p_bl = row.get('phanbaoluu', '')
                    if pd.notna(d_bl) and str(d_bl).strip(): is_bl = True; bl_txt.append(f"BL: {d_bl}")
                    if pd.notna(p_bl) and str(p_bl).strip(): is_bl = True; bl_txt.append(f"Phần: {p_bl}")

                    user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                    if _: user.set_password('cfihumg'); user.save()
                    
                    ten_k = parse_mssv_humg(mssv)
                    sv, sv_c = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': f"SV_{mssv}"})
                    if (sv_c or not sv.khoa) and ten_k:
                        sv.khoa, _ = Khoa.objects.get_or_create(ten_khoa=ten_k); sv.save()

                    LichSuThi.objects.update_or_create(
                        sinh_vien=sv, dot_thi=dot_thi, mon_thi='CDR_NGOAI_NGU',
                        defaults={
                            'diem_thanh_phan_1': pd.to_numeric(row.get('nghe'), errors='coerce'),
                            'diem_thanh_phan_2': pd.to_numeric(row.get('doc'), errors='coerce'),
                            'diem_thanh_phan_3': pd.to_numeric(row.get('viet'), errors='coerce'),
                            'diem_thanh_phan_4': pd.to_numeric(row.get('noi'), errors='coerce'),
                            'co_bao_luu': is_bl,
                            'ghi_chu': " | ".join(bl_txt) if is_bl else row.get('ghichu', '')
                        }
                    )
                    count += 1
            messages.success(request, f"✅ Đã nạp {count} bảng điểm Ngoại ngữ.")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f"❌ Lỗi: {e}")
            return redirect('students:mofi_import_diem_cdr_nn')
    return render(request, 'admin_mofi/pages/import_diem_cdr_nn.html', {'dot_this': DotThi.objects.all().order_by('-id')})

# ==========================================
# IMPORT LỊCH THI TIẾNG ANH ĐẦU VÀO (DÒ 2 LỊCH GIỐNG CĐR NN)
# ==========================================
def mofi_import_lich_thi_tdnn(request):
    # CHÈN THÊM DÒNG NÀY ĐỂ LẤY DANH SÁCH ĐỢT THI CHO DROPDOWN
    dot_this = DotThi.objects.all().order_by('-id')

    # Xử lý URL "Quay lại"
    dot_id = request.GET.get('dot')
    back_id = dot_id if dot_id else (dot_this.first().id if dot_this.exists() else 0)

    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và tải lên file.")
            return redirect('students:mofi_import_lich_thi_tdnn')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            wb = load_workbook(excel_file, read_only=True)
            visible_sheets = [s.title for s in wb.worksheets if s.sheet_state == 'visible']
            wb.close()
            excel_file.seek(0)
            sheets_dict = pd.read_excel(excel_file, sheet_name=visible_sheets, header=None)
            
            def clean_name(t):
                if pd.isna(t): return ""
                t = str(t).lower()
                for a, b in zip('àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ', 
                                'aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd'):
                    t = t.replace(a, b)
                return re.sub(r'[^a-z0-9]', '', t)

            count_new = 0
            LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi='TA_DAU_VAO').delete()

            for sheet_name, df_raw in sheets_dict.items():
                col_map = {'ngay': [], 'ca': [], 'phong': []}
                for i in range(min(15, len(df_raw))):
                    for j, val in enumerate(df_raw.iloc[i].values):
                        if pd.isna(val) or len(str(val)) > 100: continue
                        v = clean_name(val)
                        if v in ['msv', 'masinhvien', 'mssv']: col_map['mssv'] = j
                        elif v in ['stt', 'sothutu']: col_map['stt'] = j
                        elif v in ['hodem', 'ho', 'hovatendem']: col_map['ho'] = j
                        elif v == 'ten': col_map['ten'] = j
                        elif 'ngaykt' in v or 'ngaythi' in v or v == 'ngay':
                            if j not in col_map['ngay']: col_map['ngay'].append(j)
                        elif 'cakt' in v or 'cathi' in v or v == 'ca':
                            if j not in col_map['ca']: col_map['ca'].append(j)
                        elif 'phongthi' in v or 'phong' in v:
                            if j not in col_map['phong']: col_map['phong'].append(j)
                
                if 'mssv' not in col_map: continue
                
                start_row = None
                for i in range(len(df_raw)):
                    val = str(df_raw.iloc[i, col_map['mssv']]).split('.')[0].strip()
                    if re.sub(r'\D', '', val).isdigit() and len(re.sub(r'\D', '', val)) >= 5:
                        start_row = i
                        break
                if start_row is None: continue

                for i in range(start_row, len(df_raw)):
                    row = df_raw.iloc[i]
                    mssv_raw = str(row.iloc[col_map['mssv']]).split('.')[0].strip()
                    mssv = re.sub(r'\D', '', mssv_raw)
                    if not mssv or len(mssv) < 5: continue
                    
                    ho = str(row.iloc[col_map['ho']]).strip() if 'ho' in col_map and pd.notna(row.iloc[col_map['ho']]) else ""
                    ten = str(row.iloc[col_map['ten']]).strip() if 'ten' in col_map and pd.notna(row.iloc[col_map['ten']]) else ""
                    full_name = f"{ho} {ten}".strip()

                    def gv(lst, pos):
                        if len(lst) > pos and pd.notna(row.iloc[lst[pos]]):
                            val = str(row.iloc[lst[pos]]).strip()
                            return val if val.lower() != 'nan' else ""
                        return ""

                    with transaction.atomic():
                        user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                        if _: user.set_password('cfihumg'); user.save()
                        
                        ten_khoa = parse_mssv_humg(mssv)
                        defaults_sv = {'user': user, 'ho_ten': full_name}
                        if ten_khoa:
                            khoa_obj, _ = Khoa.objects.get_or_create(ten_khoa=ten_khoa)
                            defaults_sv['khoa'] = khoa_obj

                        sv, sv_created = SinhVien.objects.get_or_create(mssv=mssv, defaults=defaults_sv)
                        if not sv_created:
                            need_save = False
                            if sv.ho_ten != full_name and len(full_name) > len(sv.ho_ten):
                                sv.ho_ten = full_name
                                need_save = True
                            if not sv.khoa and ten_khoa:
                                khoa_obj, _ = Khoa.objects.get_or_create(ten_khoa=ten_khoa)
                                sv.khoa = khoa_obj
                                need_save = True
                            if need_save: sv.save()

                        LichSuThi.objects.update_or_create(
                            sinh_vien=sv, dot_thi=dot_thi, mon_thi='TA_DAU_VAO',
                            defaults={
                                'sbd': gv([col_map['stt']], 0) if 'stt' in col_map else "",
                                'ngay_thi': gv(col_map['ngay'], 0), 'ca_thi': gv(col_map['ca'], 0), 'phong_thi': gv(col_map['phong'], 0),
                                'ngay_thi_2': gv(col_map['ngay'], 1), 'ca_thi_2': gv(col_map['ca'], 1), 'phong_thi_2': gv(col_map['phong'], 1),
                            }
                        )
                    count_new += 1
            messages.success(request, f"✅ Đã nạp thành công {count_new} sinh viên TĐNN.")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e: 
            messages.error(request, f"❌ Lỗi: {e}")
            return redirect('students:mofi_import_lich_thi_tdnn')

    return render(request, 'admin_mofi/pages/import_lich_thi_tdnn.html', {
        'dot_this': dot_this, # Đã được khai báo ở đầu hàm
        'back_id': back_id
    })

@staff_member_required
def mofi_import_diem_tdnn(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            df_raw = pd.read_excel(excel_file, header=None)
            header_idx = None
            for i, row in df_raw.iterrows():
                r_str = "".join([str(v).lower() for v in row.values if pd.notna(v)])
                if 'mssv' in r_str or 'masinhvien' in r_str: header_idx = i; break
            
            df_data = df_raw.iloc[header_idx+1:].copy()
            df_data.columns = [vi_slugify(str(c)).replace('-', '') for c in df_raw.iloc[header_idx]]
            
            count = 0
            with transaction.atomic():
                for _, row in df_data.iterrows():
                    mssv = re.sub(r'\D', '', str(row.get('mssv', row.get('masinhvien', ''))).split('.')[0])
                    if not mssv or len(mssv) < 5: continue

                    is_bl = False; bl_txt = []
                    d_bl = row.get('dotbaoluu', row.get('dotbl', ''))
                    p_bl = row.get('phanbaoluu', '')
                    if pd.notna(d_bl) and str(d_bl).strip(): is_bl = True; bl_txt.append(f"BL: {d_bl}")
                    if pd.notna(p_bl) and str(p_bl).strip(): is_bl = True; bl_txt.append(f"Phần: {p_bl}")

                    user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                    if _: user.set_password('cfihumg'); user.save()
                    
                    ten_k = parse_mssv_humg(mssv)
                    sv, sv_c = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': f"SV_{mssv}"})
                    if (sv_c or not sv.khoa) and ten_k:
                        sv.khoa, _ = Khoa.objects.get_or_create(ten_khoa=ten_k); sv.save()

                    LichSuThi.objects.update_or_create(
                        sinh_vien=sv, dot_thi=dot_thi, mon_thi='TA_DAU_VAO',
                        defaults={
                            'diem_thanh_phan_1': pd.to_numeric(row.get('nghe'), errors='coerce'),
                            'diem_thanh_phan_2': pd.to_numeric(row.get('doc'), errors='coerce'),
                            'diem_thanh_phan_3': pd.to_numeric(row.get('viet'), errors='coerce'),
                            'diem_thanh_phan_4': pd.to_numeric(row.get('noi'), errors='coerce'),
                            'co_bao_luu': is_bl,
                            'ghi_chu': " | ".join(bl_txt) if is_bl else row.get('ghichu', '')
                        }
                    )
                    count += 1
            messages.success(request, f"✅ Đã nạp {count} bảng điểm Tiếng Anh đầu vào.")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f"❌ Lỗi: {e}")
            return redirect('students:mofi_import_diem_tdnn')
    return render(request, 'admin_mofi/pages/import_diem_tdnn.html', {'dot_this': DotThi.objects.all().order_by('-id')})

# ==========================================
# 8. API TICK GHÉP ĐIỂM BẢO LƯU TỪ WEB
# ==========================================
@staff_member_required
def mofi_apply_bao_luu(request, lich_thi_id):
    if request.method == 'POST':
        lt_hien_tai = get_object_or_404(LichSuThi, id=lich_thi_id)
        sv = lt_hien_tai.sinh_vien
        lt_cu_list = LichSuThi.objects.filter(sinh_vien=sv, mon_thi=lt_hien_tai.mon_thi).exclude(id=lich_thi_id).order_by('-dot_thi__thoi_gian_bat_dau')

        if not lt_cu_list.exists():
            messages.error(request, f"Lỗi: Không tìm thấy lịch sử thi cũ.")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=lt_hien_tai.dot_thi.id)

        lt_cu = lt_cu_list.first(); ghi_moi = []
        mapping = [('bao_luu_tp1', 'diem_thanh_phan_1', 'P1'), ('bao_luu_tp2', 'diem_thanh_phan_2', 'P2'), 
                   ('bao_luu_tp3', 'diem_thanh_phan_3', 'P3'), ('bao_luu_tp4', 'diem_thanh_phan_4', 'P4')]
        
        for key, field, label in mapping:
            if request.POST.get(key) == 'on' and getattr(lt_cu, field) is not None:
                setattr(lt_hien_tai, field, getattr(lt_cu, field))
                ghi_moi.append(label)

        if ghi_moi:
            lt_hien_tai.ghi_chu = f"Đã ghép ({', '.join(ghi_moi)}) từ {lt_cu.dot_thi.ten_dot}"
            lt_hien_tai.co_bao_luu = True
            lt_hien_tai.save() 
            messages.success(request, f"Đã ghép điểm thành công cho {sv.ho_ten}.")
        else:
            messages.warning(request, "Bạn chưa chọn phần điểm nào.")
        return redirect('students:mofi_dot_thi_detail', dot_thi_id=lt_hien_tai.dot_thi.id)