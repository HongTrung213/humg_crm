import pandas as pd
import io
import os
import re
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, redirect, get_object_or_404
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

from .models import SinhVien, LopBoiDuong, DangKyLop, LichSuThi, ChungChi, DotThi, Khoa, DanhMucChungChi
from .forms import DanhMucChungChiForm, UserAccountForm, GroupForm, KhoaForm
from cms.models import Slider, QuickLink, Category, Post
from django.contrib.auth.models import User, Group, Permission
from django.utils.text import slugify

# ==========================================
# SCRIPT CHẠY TỰ ĐỘNG (DỌN DẸP SLUG)
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

posts = Post.objects.filter(slug__isnull=True) | Post.objects.filter(slug='')
for p in posts:
    base_slug = vi_slugify(p.title)
    new_slug = base_slug
    counter = 1
    while Post.objects.filter(slug=new_slug).exists():
        new_slug = f"{base_slug}-{counter}"
        counter += 1
    p.slug = new_slug
    p.save()

# Hàm tiện ích làm sạch dữ liệu Excel
def clean_excel_val(val):
    if pd.isna(val): return ""
    if isinstance(val, float):
        if val.is_integer(): return str(int(val))
    return str(val).strip()

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
            # ĐÃ SỬA: Thay -dot_thi__ngay_thi thành -dot_thi__thoi_gian_bat_dau
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

        # ĐÃ SỬA: Thay -dot_thi__ngay_thi thành -dot_thi__thoi_gian_bat_dau
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
# 3. QUẢN TRỊ ADMIN (SINH VIÊN & DANH MỤC)
# ==========================================
@login_required
def admin_mofi_dashboard(request):
    if not request.user.is_staff: return redirect('students:home')
    khoas = Khoa.objects.prefetch_related('sinh_vien_list__lich_su_thi', 'sinh_vien_list__ds_chung_chi__danh_muc').all()
    thong_ke_khoa = []
    for k in khoas:
        ds_sv = k.sinh_vien_list.all()
        thong_ke_khoa.append({
            'ten_khoa': k.ten_khoa, 'tong_sv': ds_sv.count(),
            'dat_cntt': sum(1 for sv in ds_sv if sv.check_dat_tin_hoc),
            'dat_nn_ra': sum(1 for sv in ds_sv if sv.check_dat_ngoai_ngu),
            'dat_nn_vao': sum(1 for sv in ds_sv if sv.check_dat_dau_vao),
        })
    thong_ke_khoa.sort(key=lambda x: x['tong_sv'], reverse=True)
    
    context = {
        'total_students': SinhVien.objects.count(),
        'active_classes': LopBoiDuong.objects.filter(trang_thai=True).count(),
        'pending_registrations': DangKyLop.objects.filter(trang_thai='CHO_DUYET').count(),
        'certificates_issued': ChungChi.objects.count(),
        'recent_activities': DangKyLop.objects.select_related('sinh_vien', 'lop_hoc').order_by('-thoi_gian_dk')[:5],
        'thong_ke_khoa': thong_ke_khoa,
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
    search_query, sort_by, active_tab = request.GET.get('q', '').strip(), request.GET.get('sort', '-ngay_cap_nhat'), request.GET.get('tab', 'tdnn')

    def get_filtered_qs(mon_thi_code):
        qs = LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi=mon_thi_code).select_related('sinh_vien')
        if search_query: qs = qs.filter(Q(sinh_vien__mssv__icontains=search_query) | Q(sinh_vien__ho_ten__icontains=search_query))
        return qs.order_by(sort_by)

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
    for lt in LichSuThi.objects.filter(dot_thi=dot_thi).select_related('sinh_vien').order_by('sbd'):
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
            # 1. Đọc tất cả sheet hiển thị
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
            # Xóa lịch sử cũ của môn Tin học trong đợt này để tránh trùng lặp
            LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi='CDR_TIN_HOC').delete()

            for sheet_name, df_raw in sheets_dict.items():
                col_map = {'ngay': [], 'ca': [], 'phong': []}
                
                # Quét 15 dòng đầu để tìm tiêu đề cột (Bỏ qua Ghi chú dài > 100 ký tự)
                for i in range(min(15, len(df_raw))):
                    for j, val in enumerate(df_raw.iloc[i].values):
                        if pd.isna(val) or len(str(val)) > 100: continue
                        
                        v = clean_col(val)
                        if v in ['msv', 'masinhvien', 'mssv']: col_map['mssv'] = j
                        elif v in ['stt', 'sothutu']: col_map['stt'] = j
                        elif v in ['hodem', 'ho', 'hovatendem']: col_map['ho'] = j
                        elif v == 'ten': col_map['ten'] = j
                        elif 'hovaten' in v or 'hoten' in v: col_map['hoten'] = j
                        elif 'ngaykt' in v or 'ngaythi' in v or v == 'ngay':
                            if j not in col_map['ngay']: col_map['ngay'].append(j)
                        elif 'cakt' in v or 'cathi' in v or v == 'ca':
                            if j not in col_map['ca']: col_map['ca'].append(j)
                        elif 'phongthi' in v or 'phong' in v:
                            if j not in col_map['phong']: col_map['phong'].append(j)
                
                if 'mssv' not in col_map: continue
                
                # Tìm dòng bắt đầu có MSSV thật (dạng số >= 5 ký tự)
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
                    
                    # Xử lý Họ tên
                    if 'hoten' in col_map and pd.notna(row.iloc[col_map['hoten']]):
                        ho_ten = str(row.iloc[col_map['hoten']]).strip()
                    else:
                        ho = str(row.iloc[col_map['ho']]).strip() if 'ho' in col_map and pd.notna(row.iloc[col_map['ho']]) else ""
                        ten = str(row.iloc[col_map['ten']]).strip() if 'ten' in col_map and pd.notna(row.iloc[col_map['ten']]) else ""
                        ho_ten = f"{ho} {ten}".strip() or f"SV_{mssv}"

                    def gv(lst, pos):
                        if len(lst) > pos and pd.notna(row.iloc[lst[pos]]):
                            val = str(row.iloc[lst[pos]]).strip()
                            return val if val.lower() != 'nan' else ""
                        return ""

                    with transaction.atomic():
                        user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                        if _: user.set_password('cfihumg'); user.save()
                        
                        sv, _ = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': ho_ten})
                        if sv.ho_ten != ho_ten and len(ho_ten) > len(sv.ho_ten):
                            sv.ho_ten = ho_ten
                            sv.save()

                        LichSuThi.objects.update_or_create(
                            sinh_vien=sv, dot_thi=dot_thi, mon_thi='CDR_TIN_HOC',
                            defaults={
                                'sbd': gv([col_map['stt']], 0) if 'stt' in col_map else "",
                                'ngay_thi': gv(col_map['ngay'], 0),
                                'ca_thi': gv(col_map['ca'], 0),
                                'phong_thi': gv(col_map['phong'], 0),
                            }
                        )
                    total_count += 1

            messages.success(request, f"✅ Đã nạp thành công {total_count} lịch thi CNTT đợt này.")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
            
        except Exception as e:
            messages.error(request, f"❌ Lỗi: {str(e)}")
            return redirect('students:mofi_dot_thi_list')

    return render(request, 'admin_mofi/pages/import_lich_thi_cntt.html', {'dot_this': DotThi.objects.all().order_by('-id')})


import re
import pandas as pd
from openpyxl import load_workbook
from django.db import transaction
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User

# ==========================================
# IMPORT LỊCH THI CĐR NGOẠI NGỮ
# ==========================================
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
            # 1. Đọc file và lọc sheet hiển thị
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
            
            # --- BƯỚC QUAN TRỌNG: XÓA RÁC CŨ ---
            # Xóa sạch lịch thi Ngoại ngữ của đợt này để nạp mới hoàn toàn
            LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi='CDR_NGOAI_NGU').delete()

            for sheet_name, df_raw in sheets_dict.items():
                col_map = {'ngay': [], 'ca': [], 'phong': []}
                
                # BƯỚC 2: Dò tìm tọa độ chuẩn (ĐÃ NÂNG CẤP BẢO VỆ CHỐNG GHI CHÚ)
                for i in range(min(15, len(df_raw))):
                    for j, val in enumerate(df_raw.iloc[i].values):
                        # BỎ QUA NGAY CÁC Ô TRỐNG HOẶC ĐOẠN VĂN GHI CHÚ DÀI (>100 ký tự)
                        if pd.isna(val) or len(str(val)) > 100: 
                            continue
                            
                        v = clean_name(val)
                        if v in ['msv', 'masinhvien', 'mssv']: col_map['mssv'] = j
                        elif v in ['stt', 'sothutu']: col_map['stt'] = j # Lấy STT làm SBD
                        elif v in ['hodem', 'ho', 'hovatendem']: col_map['ho'] = j
                        elif v == 'ten': col_map['ten'] = j
                        
                        # Cải tiến thuật toán bắt chính xác Ngày, Ca, Phòng
                        elif 'ngaykt' in v or 'ngaythi' in v or v == 'ngay': 
                            if j not in col_map['ngay']: col_map['ngay'].append(j)
                        elif 'cakt' in v or 'cathi' in v or v == 'ca': 
                            if j not in col_map['ca']: col_map['ca'].append(j)
                        elif 'phongthi' in v or 'phong' in v: 
                            if j not in col_map['phong']: col_map['phong'].append(j)
                
                if 'mssv' not in col_map: continue
                
                # Tìm dòng bắt đầu chứa dữ liệu Sinh viên (Bỏ qua các dòng tiêu đề)
                start_row = None
                for i in range(len(df_raw)):
                    val = str(df_raw.iloc[i, col_map['mssv']]).split('.')[0].strip()
                    if re.sub(r'\D', '', val).isdigit() and len(re.sub(r'\D', '', val)) >= 5:
                        start_row = i
                        break
                
                if start_row is None: continue

                # Nạp dữ liệu từng dòng
                for i in range(start_row, len(df_raw)):
                    row = df_raw.iloc[i]
                    mssv = re.sub(r'\D', '', str(row.iloc[col_map['mssv']]).split('.')[0].strip())
                    if not mssv or len(mssv) < 5: continue
                    
                    # GHÉP HỌ VÀ TÊN ĐẦY ĐỦ
                    ho = str(row.iloc[col_map['ho']]).strip() if 'ho' in col_map and pd.notna(row.iloc[col_map['ho']]) else ""
                    ten = str(row.iloc[col_map['ten']]).strip() if 'ten' in col_map and pd.notna(row.iloc[col_map['ten']]) else ""
                    full_name = f"{ho} {ten}".strip()
                    
                    # Lấy STT để làm SBD cho đẹp
                    stt_val = str(row.iloc[col_map['stt']]).split('.')[0].strip() if 'stt' in col_map else ""

                    with transaction.atomic():
                        user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                        if _: user.set_password('cfihumg'); user.save()
                        
                        sv, _ = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': full_name})
                        
                        # Cập nhật lại tên nếu tên cũ bị sai
                        if sv.ho_ten != full_name and len(full_name) > len(sv.ho_ten):
                            sv.ho_ten = full_name
                            sv.save()

                        # Bóc tách 2 lịch thi (Máy và Vấn đáp) an toàn
                        def gv(lst, pos):
                            if len(lst) > pos and pd.notna(row.iloc[lst[pos]]):
                                val = str(row.iloc[lst[pos]]).strip()
                                # Chống lỗi bị đọc thành chữ 'nan'
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

            messages.success(request, f"✅ Đã dọn rác và nạp mới {total_count} sinh viên Ngoại ngữ thành công! (Cập nhật đủ Ngày - Ca - Phòng)")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
            
        except Exception as e:
            messages.error(request, f"❌ Lỗi xử lý file Excel: {str(e)}")
            return redirect(f"{reverse('students:mofi_import_lich_thi_nn')}?dot={dot_thi_id}")

    return render(request, 'admin_mofi/pages/import_lich_thi_nn.html', {'dot_this': DotThi.objects.all().order_by('-id')})


import re
import pandas as pd
from openpyxl import load_workbook
from django.db import transaction

@staff_member_required
def mofi_import_diem_cntt(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và tải lên file Excel.")
            return redirect('students:mofi_import_diem_cntt')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            # --- BƯỚC 1: LỌC CHỈ LẤY CÁC SHEET ĐANG HIỂN THỊ (VISIBLE) ---
            wb = load_workbook(excel_file, read_only=True)
            visible_sheets = [sheet.title for sheet in wb.worksheets if sheet.sheet_state == 'visible']
            wb.close()
            
            if not visible_sheets:
                messages.error(request, "❌ File Excel không có sheet nào đang hiển thị!")
                return redirect('students:mofi_import_diem_cntt')

            # Đọc dữ liệu từ các sheet hiển thị
            excel_file.seek(0) # Reset con trỏ file sau khi openpyxl đọc
            sheets_dict = pd.read_excel(excel_file, sheet_name=visible_sheets, header=None)
            
            # --- BƯỚC 2: CÔNG CỤ LÀM SẠCH VÀ CHUẨN HÓA ---
            def clean_col_name(text):
                if pd.isna(text): return ""
                text = str(text).lower()
                text = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', text)
                text = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', text)
                text = re.sub(r'[ìíịỉĩ]', 'i', text)
                text = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', text)
                text = re.sub(r'[ùúụủũưừứựửữ]', 'u', text)
                text = re.sub(r'[ỳýỵỷỹ]', 'y', text)
                text = re.sub(r'đ', 'd', text)
                return re.sub(r'[^a-z0-9]', '', text)

            total_count = 0
            sheets_processed = []

            with transaction.atomic():
                # --- BƯỚC 3: XỬ LÝ TỪNG SHEET HIỂN THỊ ---
                for sheet_name, df_raw in sheets_dict.items():
                    # Tìm dòng Header
                    header_row_index = None
                    for i, row in df_raw.iterrows():
                        row_str = "".join([clean_col_name(v) for v in row.values])
                        # Kiểm tra xem dòng này có chứa 'masinhvien' và ('tracnghiem' hoặc 'thuchanh')
                        if ('masinhvien' in row_str or 'mssv' in row_str) and \
                           ('tracnghiem' in row_str or 'thuchanh' in row_str):
                            header_row_index = i
                            break
                    
                    if header_row_index is None:
                        continue # Sheet rác hoặc sheet thống kê ko có bảng điểm -> Bỏ qua

                    # Cắt dữ liệu từ dòng header trở xuống
                    raw_columns = df_raw.iloc[header_row_index].values
                    df_data = df_raw.iloc[header_row_index + 1:].copy()
                    
                    # Gán tên cột đã chuẩn hóa
                    df_data.columns = [clean_col_name(c) or f"col_{j}" for j, c in enumerate(raw_columns)]

                    mssv_col = next((c for c in df_data.columns if 'masinhvien' in c or 'mssv' in c), None)
                    if not mssv_col: continue

                    # --- BƯỚC 4: NẠP SINH VIÊN VÀ ĐIỂM ---
                    for _, row in df_data.iterrows():
                        if pd.isna(row[mssv_col]): continue
                        
                        # Lấy MSSV sạch (chỉ lấy số)
                        mssv_raw = str(row[mssv_col]).split('.')[0].strip()
                        mssv = re.sub(r'\D', '', mssv_raw)
                        if not mssv or len(mssv) < 5: continue

                        # Đồng bộ User
                        user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                        if _: user.set_password('cfihumg'); user.save()
                        
                        # Lấy Họ tên (vẫn lấy từ cột gốc trong row để ko bị mất dấu)
                        name_col = next((c for c in df_data.columns if 'hovaten' in c or 'hoten' in c), None)
                        ho_ten_val = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else f"SV_{mssv}"
                        if ho_ten_val.lower() in ['nan', 'none', '']: ho_ten_val = f"SV_{mssv}"
                        
                        sv, _ = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': ho_ten_val})

                        # Hàm lấy điểm an toàn
                        def get_val(keys):
                            col = next((c for c in df_data.columns if any(k in c for k in keys)), None)
                            if col and pd.notna(row[col]):
                                try: return float(row[col])
                                except: return None
                            return None

                        defaults = {
                            'diem_thanh_phan_1': get_val(['tracnghiem', 'lythuyet']),
                            'diem_thanh_phan_2': get_val(['thuchanh']),
                            'diem_tong': get_val(['danhgia', 'tong']),
                        }
                        
                        xl_col = next((c for c in df_data.columns if 'xeploai' in c or 'ketqua' in c), None)
                        if xl_col and pd.notna(row[xl_col]):
                            val_xl = str(row[xl_col]).strip()
                            if val_xl.lower() not in ['nan', 'none']: defaults['xep_loai'] = val_xl

                        LichSuThi.objects.update_or_create(
                            sinh_vien=sv, dot_thi=dot_thi, mon_thi='CDR_TIN_HOC',
                            defaults=defaults
                        )
                        total_count += 1
                    
                    sheets_processed.append(sheet_name)

            if total_count > 0:
                messages.success(request, f"✅ Đã nạp thành công {total_count} sinh viên từ {len(sheets_processed)} sheet hiển thị ({', '.join(sheets_processed)}).")
            else:
                messages.warning(request, "⚠ Không tìm thấy dữ liệu hợp lệ trong các sheet đang hiển thị.")
                
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)

        except Exception as e:
            messages.error(request, f"❌ Lỗi: {str(e)}")
            return redirect('students:mofi_import_diem_cntt')

    return render(request, 'admin_mofi/pages/import_diem_cntt.html', {'dot_this': DotThi.objects.all().order_by('-id')})


@staff_member_required
def mofi_import_diem_cdr_nn(request):
    if request.method == 'POST':
        dot_thi_id, excel_file = request.POST.get('dot_thi'), request.FILES.get('excel_file')
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và tải lên file Excel.")
            return redirect('students:mofi_import_diem_cdr_nn')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        try:
            df_raw = pd.read_excel(excel_file, header=None)
            header_row = next((i for i, row in df_raw.iterrows() if any('mã sinh viên' in str(v).lower() or 'mssv' in str(v).lower() for v in row.values)), 0)
            df = pd.read_excel(excel_file, header=header_row)
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            count_update_diem = 0
            with transaction.atomic():
                for _, row in df.iterrows():
                    c_mssv = next((c for c in df.columns if 'mã sinh viên' in c or 'mssv' in c), None)
                    if not c_mssv or pd.isna(row[c_mssv]): continue
                    mssv = clean_excel_val(row[c_mssv])
                    if not mssv: continue
                    
                    # --- CHIẾN THUẬT GHÉP TÊN MỚI ---
                    c_hoten = next((c for c in df.columns if 'họ và tên' in c or 'họ tên' in c), None)
                    c_ho = next((c for c in df.columns if 'họ' in str(c) and 'tên' not in str(c)), None)
                    c_ten = next((c for c in df.columns if 'tên' in str(c) and 'họ' not in str(c)), None)
                    
                    ho_ten_full = ""
                    if c_hoten:
                        ho_ten_full = clean_excel_val(row[c_hoten])
                    elif c_ho and c_ten:
                        ho_ten_full = f"{clean_excel_val(row[c_ho])} {clean_excel_val(row[c_ten])}".strip()
                    else:
                        # Trường hợp giáo vụ để cột "Họ đệm" và cột tiếp theo là "Tên" nhưng ko đặt tiêu đề chuẩn
                        ho_val = clean_excel_val(row[c_ho]) if c_ho else ""
                        ho_ten_full = ho_val if ho_val else f"SV_{mssv}"

                    user, u_created = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                    if u_created: user.set_password('cfihumg'); user.save()
                    
                    sv, sv_created = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': ho_ten_full})
                    
                    # CẬP NHẬT TÊN: Nếu tên hiện tại ngắn hơn tên trong file (do bị mất tên trước đó), cập nhật lại!
                    if not sv_created and len(sv.ho_ten) < len(ho_ten_full):
                        sv.ho_ten = ho_ten_full
                        sv.save()

                    def get_score(key):
                        col = next((c for c in df.columns if key in c), None)
                        return pd.to_numeric(row[col], errors='coerce') if col and pd.notna(row[col]) else None

                    defaults = {
                        'diem_thanh_phan_1': get_score('nghe'),
                        'diem_thanh_phan_2': get_score('đọc'),
                        'diem_thanh_phan_3': get_score('viết'),
                        'diem_thanh_phan_4': get_score('nói'),
                        'diem_tong': get_score('đánh giá') or get_score('tổng') or get_score('phương án'),
                    }
                    
                    c_xl = next((c for c in df.columns if 'xếp loại' in c or 'kết quả' in c), None)
                    c_gc = next((c for c in df.columns if 'ghi chú' in c), None)
                    if c_xl: defaults['xep_loai'] = clean_excel_val(row[c_xl])
                    if c_gc: defaults['ghi_chu'] = clean_excel_val(row[c_gc])

                    LichSuThi.objects.update_or_create(
                        sinh_vien=sv, dot_thi=dot_thi, mon_thi='CDR_NGOAI_NGU', 
                        defaults=defaults
                    )
                    count_update_diem += 1

            messages.success(request, f"✅ Đã nạp & sửa tên cho {count_update_diem} sinh viên Ngoại ngữ!")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f"❌ Lỗi: {e}")
            return redirect('students:mofi_import_diem_cdr_nn')
    return render(request, 'admin_mofi/pages/import_diem_cdr_nn.html', {'dot_this': DotThi.objects.all().order_by('-id')})

@staff_member_required
def mofi_import_diem_tdnn(request):
    if request.method == 'POST':
        dot_thi_id, excel_file = request.POST.get('dot_thi'), request.FILES.get('excel_file')
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        connection.close()

        try:
            df_raw = pd.read_excel(excel_file, header=None)
            header_idx = next((i for i, row in df_raw.iterrows() if any('mã sinh viên' in str(v).lower() for v in row.values)), 0)
            df = pd.read_excel(excel_file, header=header_idx)
            df.columns = [str(c).lower().strip() for c in df.columns]

            c_mssv = next((c for c in df.columns if 'mã sinh viên' in c or 'mssv' in c), None)
            if not c_mssv: raise Exception("Không tìm thấy cột Mã sinh viên trong file.")

            mssv_list = df[c_mssv].dropna().astype(str).str.split('.').str[0].str.strip().tolist()
            users_dict = {u.username: u for u in User.objects.filter(username__in=mssv_list)}
            sv_dict = {sv.mssv: sv for sv in SinhVien.objects.filter(mssv__in=mssv_list)}

            lich_su_thi_objects = []
            d_chuan, d_liet = dot_thi.diem_chuan_ngoai_ngu, dot_thi.diem_liet_ngoai_ngu

            with transaction.atomic():
                LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi='TA_DAU_VAO').delete()

                for index, row in df.iterrows():
                    mssv = str(row[c_mssv]).split('.')[0].strip()
                    if not mssv or mssv == 'nan': continue

                    if mssv not in users_dict:
                        user = User.objects.create_user(username=mssv, password='cfihumg', is_active=True)
                        users_dict[mssv] = user
                    user = users_dict[mssv]

                    if mssv not in sv_dict:
                        c_ho_idx = next((i for i, c in enumerate(df.columns) if 'họ và tên' in c or 'họ tên' in c), None)
                        if c_ho_idx is not None:
                            ho_val = str(row.iloc[c_ho_idx]).replace('nan', '').strip()
                            ten_val = str(row.iloc[c_ho_idx + 1]).replace('nan', '').strip()
                            full_name = f"{ho_val} {ten_val}".strip() or f"Sinh viên {mssv}"
                        else:
                            full_name = f"Sinh viên {mssv}"
                        sv = SinhVien.objects.create(mssv=mssv, user=user, ho_ten=full_name)
                        sv_dict[mssv] = sv
                    sv = sv_dict[mssv]

                    def get_d(key):
                        col = next((c for c in df.columns if key in c), None)
                        return pd.to_numeric(row[col], errors='coerce') if col else None

                    nghe, doc, viet, noi = get_d('nghe'), get_d('đọc'), get_d('viết'), get_d('nói')
                    xep_loai, ghi_chu = str(row.get('xếp loại', '')).replace('nan', '').strip(), str(row.get('ghi chú', '')).replace('nan', '').strip()

                    valid_diems = [d for d in [nghe, doc, viet, noi] if pd.notna(d)]
                    diem_tong = round(sum(valid_diems), 2) if valid_diems else 0

                    is_pass = False
                    xl_lower, gc_lower = xep_loai.lower(), ghi_chu.lower()
                    if any(k in xl_lower or k in gc_lower for k in ['vắng', 'bỏ thi', 'đình chỉ', 'không đạt']): is_pass = False
                    elif any(k in xl_lower for k in ['đủ điều kiện', 'đạt', 'pass', 'b1', 'b2', 'a2', 'c1']): is_pass = True
                    else:
                        bi_liet = any(d <= d_liet for d in valid_diems) if d_liet >= 0 else False
                        if not bi_liet and diem_tong >= d_chuan: is_pass = True

                    lich_su_thi_objects.append(LichSuThi(
                        sinh_vien=sv, dot_thi=dot_thi, mon_thi='TA_DAU_VAO',
                        diem_thanh_phan_1=nghe, diem_thanh_phan_2=doc, diem_thanh_phan_3=viet, diem_thanh_phan_4=noi,
                        diem_tong=diem_tong, xep_loai=xep_loai, ghi_chu=ghi_chu, ket_qua_dat=is_pass
                    ))

                LichSuThi.objects.bulk_create(lich_su_thi_objects, batch_size=500)
            messages.success(request, f"Đã nạp siêu tốc {len(lich_su_thi_objects)} bản ghi điểm thi!")
        except Exception as e:
            messages.error(request, f"Lỗi xử lý file: {str(e)}")
            
        return redirect('students:mofi_import_diem_tdnn')
    return render(request, 'admin_mofi/pages/import_diem_tdnn.html', {'dot_this': DotThi.objects.all().order_by('-id')})

# ==========================================
# IMPORT LỊCH THI TIẾNG ANH ĐẦU VÀO (DÒ 2 LỊCH GIỐNG CĐR NN)
# ==========================================
import re
import pandas as pd
from openpyxl import load_workbook
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.models import User
from .models import DotThi, SinhVien, LichSuThi

def mofi_import_lich_thi_tdnn(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và tải lên file.")
            return redirect('students:mofi_import_lich_thi_tdnn')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            # 1. Đọc tất cả các sheet đang hiển thị
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
            # XÓA DỮ LIỆU CŨ ĐỂ NẠP MỚI (TRÁNH TRÙNG LẶP)
            LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi='TA_DAU_VAO').delete()

            for sheet_name, df_raw in sheets_dict.items():
                col_map = {'ngay': [], 'ca': [], 'phong': []}
                
                # 2. Dò tìm tọa độ cột tiêu đề (Chặn Ghi chú dài)
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
                
                # 3. Tìm dòng dữ liệu đầu tiên (Dựa trên MSSV là số)
                start_row = None
                for i in range(len(df_raw)):
                    val = str(df_raw.iloc[i, col_map['mssv']]).split('.')[0].strip()
                    if re.sub(r'\D', '', val).isdigit() and len(re.sub(r'\D', '', val)) >= 5:
                        start_row = i
                        break
                
                if start_row is None: continue

                # 4. Nạp dữ liệu
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
                        
                        sv, _ = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': full_name})
                        if sv.ho_ten != full_name and len(full_name) > len(sv.ho_ten):
                            sv.ho_ten = full_name
                            sv.save()

                        LichSuThi.objects.update_or_create(
                            sinh_vien=sv, dot_thi=dot_thi, mon_thi='TA_DAU_VAO',
                            defaults={
                                'sbd': gv([col_map['stt']], 0) if 'stt' in col_map else "",
                                'ngay_thi': gv(col_map['ngay'], 0), 
                                'ca_thi': gv(col_map['ca'], 0), 
                                'phong_thi': gv(col_map['phong'], 0),
                                'ngay_thi_2': gv(col_map['ngay'], 1), 
                                'ca_thi_2': gv(col_map['ca'], 1), 
                                'phong_thi_2': gv(col_map['phong'], 1),
                            }
                        )
                    count_new += 1
                    
            messages.success(request, f"✅ Đã nạp thành công {count_new} sinh viên TĐNN (Đã bóc tách Lịch Máy + Lịch Nói)!")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
            
        except Exception as e: 
            messages.error(request, f"❌ Lỗi: {e}")
            return redirect('students:mofi_import_lich_thi_tdnn')
            
    return render(request, 'admin_mofi/pages/import_lich_thi_tdnn.html', {'dot_this': DotThi.objects.all().order_by('-id')})