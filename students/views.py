import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Case, When, Value, IntegerField, Count
from .models import SinhVien, LopBoiDuong, DangKyLop, LichSuThi, ChungChi, DotThi, Khoa, DanhMucChungChi
from django.contrib.admin.views.decorators import staff_member_required
from .models import DanhMucChungChi
from .forms import DanhMucChungChiForm
from cms.models import Slider, QuickLink 
from cms.models import Category, Post, QuickLink

from django.contrib.auth.models import User, Group
from django.contrib.admin.views.decorators import staff_member_required
from .forms import UserAccountForm # Nhớ import form vừa tạo
from .forms import UserAccountForm, GroupForm
from django.utils import timezone
from cms.models import Post
from django.utils.text import slugify
import re

# Khai báo lại hàm tạo slug tiếng Việt cho Shell
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

# Lọc tất cả các bài viết đang bị rỗng slug
posts = Post.objects.filter(slug__isnull=True) | Post.objects.filter(slug='')

print(f"Tìm thấy {posts.count()} bài viết bị rỗng slug.")

# Cập nhật lại slug cho chúng
for p in posts:
    base_slug = vi_slugify(p.title)
    new_slug = base_slug
    counter = 1
    while Post.objects.filter(slug=new_slug).exists():
        new_slug = f"{base_slug}-{counter}"
        counter += 1
    p.slug = new_slug
    p.save()
    print(f"Đã cập nhật slug cho bài: {p.title}")
# ==========================================
# 1. PHÂN HỆ CÔNG CỘNG (CỔNG THÔNG TIN SINH VIÊN)
# ==========================================
def home(request):
    # 1. Lấy dữ liệu Banner Slider 
    slider_posts = Slider.objects.filter(is_active=True).order_by('order')

    # 2. Lấy danh sách Liên kết nhanh (Quick Links)
    quick_links = QuickLink.objects.filter(is_active=True).order_by('order')

    # 3. Xử lý các khối Tin tức (Block News)
    # CHÚ Ý: Chỉ lấy những danh mục được Admin tick chọn "Hiển thị trên trang chủ"
    categories_on_home = Category.objects.filter(is_active=True, show_on_homepage=True).order_by('id')
    
    home_blocks = []
    for cat in categories_on_home:
        # Lấy tối đa 5 bài viết mới nhất đã xuất bản thuộc danh mục này
        posts = Post.objects.filter(category=cat, is_published=True).order_by('-created_at')[:5]
        
        # Chỉ đẩy ra HTML những danh mục có ít nhất 1 bài viết
        if posts.exists():
            home_blocks.append({
                'category': cat,
                'posts': posts
            })

    # Đóng gói dữ liệu và gửi ra HTML
    context = {
        'slider_posts': slider_posts,
        'quick_links': quick_links,
        'home_blocks': home_blocks,
    }
    
    return render(request, 'students/home.html', context)

def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk, is_published=True)
    # Lấy các tin liên quan cùng danh mục
    related_posts = Post.objects.filter(category=post.category, is_published=True).exclude(pk=pk)[:5]
    return render(request, 'students/post_detail.html', {
        'post': post,
        'related_posts': related_posts
    })

def tra_cuu(request):
    query_mssv = request.GET.get('mssv', '').strip()
    sinh_vien, lich_thi_sap_toi, ket_qua_thi = None, None, None
    thong_bao = None

    if query_mssv:
        try:
            sinh_vien = SinhVien.objects.get(mssv=query_mssv)
            # Lấy toàn bộ lịch sử thi của sinh viên này
            toan_bo_lich_thi = sinh_vien.lich_su_thi.all().order_by('-dot_thi__ngay_thi')
            
            # Phân loại: Chưa có điểm là "Lịch thi sắp tới", có điểm rồi là "Kết quả"
            lich_thi_sap_toi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=True)
            ket_qua_thi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=False)
            
        except SinhVien.DoesNotExist:
            thong_bao = f"Không tìm thấy dữ liệu cho mã số sinh viên: {query_mssv}"
            
    return render(request, 'students/tra_cuu.html', {
        'sinh_vien': sinh_vien, 
        'query_mssv': query_mssv, 
        'thong_bao': thong_bao, 
        'lich_thi_sap_toi': lich_thi_sap_toi,
        'ket_qua_thi': ket_qua_thi
    })
# ==========================================
# 2. XÁC THỰC
# ==========================================
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
# 3. PORTAL SINH VIÊN
# ==========================================
@login_required
def dashboard(request):
    try:
        # 1. Lấy thông tin sinh viên
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
        
        # 2. Lấy dữ liệu Lớp bồi dưỡng & Danh mục
        ds_dang_ky = DangKyLop.objects.filter(sinh_vien=sinh_vien).order_by('-thoi_gian_dk')
        khoas = Khoa.objects.all().order_by('ten_khoa')
        danh_muc_cc = DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi')

        # 3. Lấy dữ liệu CMS (Slider, QuickLink)
        sliders = Slider.objects.filter(is_active=True).order_by('order')
        quick_links = QuickLink.objects.filter(is_active=True).order_by('order')

        # 4. Lấy dữ liệu Lịch thi & Kết quả thi
        toan_bo_lich_thi = sinh_vien.lich_su_thi.all().order_by('-dot_thi__ngay_thi')
        lich_thi_sap_toi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=True)
        ket_qua_thi = toan_bo_lich_thi.filter(diem_thanh_phan_1__isnull=False)

        # 5. Bơm toàn bộ dữ liệu ra HTML
        return render(request, 'students/dashboard.html', {
            'sinh_vien': sinh_vien, 
            'ds_dang_ky': ds_dang_ky,
            'khoas': khoas,
            'danh_muc_cc': danh_muc_cc,
            'sliders': sliders,
            'quick_links': quick_links,
            'lich_thi_sap_toi': lich_thi_sap_toi,
            'ket_qua_thi': ket_qua_thi
        })
        
    except SinhVien.DoesNotExist:
        messages.error(request, "Hồ sơ cá nhân chưa được khởi tạo trên hệ thống.")
        return redirect('students:home')
    
@login_required
def quick_add_cert_portal(request):
    if request.method == 'POST':
        try:
            sinh_vien = SinhVien.objects.get(mssv=request.user.username)
            danh_muc = get_object_or_404(DanhMucChungChi, id=request.POST.get('danh_muc_id'))
            ChungChi.objects.create(
                sinh_vien=sinh_vien, danh_muc=danh_muc,
                so_hieu=request.POST.get('so_hieu'), ngay_cap=request.POST.get('ngay_cap'),
                file_minh_chung=request.FILES.get('file_minh_chung'), trang_thai='CHO'
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
    try:
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
    except SinhVien.DoesNotExist:
        return redirect('students:home')

    if request.method == 'POST':
        lop_id = request.POST.get('lop_id')
        file_mc = request.FILES.get('file_minh_chung')
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

# ==========================================
# 4. QUẢN TRỊ ADMIN (SINH VIÊN & THỐNG KÊ)
# ==========================================
from django.db.models import Count
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import SinhVien, LopBoiDuong, DangKyLop, Khoa, ChungChi

@login_required
def admin_mofi_dashboard(request):
    if not request.user.is_staff: 
        return redirect('students:home')

    total_students = SinhVien.objects.count()
    
    # Lấy danh sách Khoa kèm theo dữ liệu quan hệ của sinh viên để tối ưu hiệu suất truy vấn
    khoas = Khoa.objects.prefetch_related(
        'sinh_vien_list__lich_su_thi', 
        'sinh_vien_list__ds_chung_chi__danh_muc'
    ).all()
    
    thong_ke_khoa = []
    for k in khoas:
        danh_sach_sv = k.sinh_vien_list.all()
        tong_sv = danh_sach_sv.count()
        
        # Tính toán các chỉ số đạt chuẩn dựa trên @property của SinhVien
        dat_cntt = sum(1 for sv in danh_sach_sv if sv.check_dat_tin_hoc)
        dat_nn_ra = sum(1 for sv in danh_sach_sv if sv.check_dat_ngoai_ngu)
        dat_nn_vao = sum(1 for sv in danh_sach_sv if sv.check_dat_dau_vao)
        
        thong_ke_khoa.append({
            'ten_khoa': k.ten_khoa,
            'tong_sv': tong_sv,
            'dat_cntt': dat_cntt,
            'dat_nn_ra': dat_nn_ra,
            'dat_nn_vao': dat_nn_vao,
        })
        
    # Sắp xếp danh sách giảm dần theo tổng số lượng sinh viên
    thong_ke_khoa.sort(key=lambda x: x['tong_sv'], reverse=True)

    context = {
        'total_students': total_students,
        'active_classes': LopBoiDuong.objects.filter(trang_thai=True).count(),
        'pending_registrations': DangKyLop.objects.filter(trang_thai='CHO_DUYET').count(),
        'certificates_issued': ChungChi.objects.count(), # Có thể điều chỉnh thành số lượng chứng chỉ Đạt nếu cần
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
        'student': student, 
        'ds_dang_ky': student.ds_dang_ky_lop.all().order_by('-thoi_gian_dk'), 
        'lich_su_thi': student.lich_su_thi.all().order_by('-ngay_cap_nhat'),
        'danh_muc_cc': danh_muc_cc
    })

@login_required
def student_add(request):
    if not request.user.is_staff: return redirect('students:home')
    if request.method == 'POST':
        mssv = request.POST.get('mssv', '').strip()
        khoa_id = request.POST.get('khoa') # Lấy ID từ select
        SinhVien.objects.create(
            mssv=mssv, ho_ten=request.POST.get('ho_ten'),
            khoa_id=khoa_id, lop=request.POST.get('lop'),
            so_dien_thoai=request.POST.get('so_dien_thoai'),
            email_ca_nhan=request.POST.get('email_ca_nhan'),
            anh_dai_dien=request.FILES.get('anh_dai_dien')
        )
        messages.success(request, "Thêm sinh viên thành công!")
        return redirect('students:student_list')
    
    khoas = Khoa.objects.all().order_by('ten_khoa')
    return render(request, 'admin_mofi/students/student_form.html', {'khoas': khoas})

# Cập nhật hàm Edit Sinh viên (Admin)
@login_required
def student_edit(request, id):
    if not request.user.is_staff: return redirect('students:home')
    student = get_object_or_404(SinhVien, id=id)
    if request.method == 'POST':
        student.khoa_id = request.POST.get('khoa')
        student.ho_ten = request.POST.get('ho_ten')
        student.lop = request.POST.get('lop')
        student.so_dien_thoai = request.POST.get('so_dien_thoai')
        student.email_ca_nhan = request.POST.get('email_ca_nhan')
        if request.FILES.get('anh_dai_dien'): student.anh_dai_dien = request.FILES.get('anh_dai_dien')
        student.save()
        messages.success(request, "Cập nhật thành công!")
        return redirect('students:student_list')
    
    khoas = Khoa.objects.all().order_by('ten_khoa')
    return render(request, 'admin_mofi/students/student_form.html', {'student': student, 'khoas': khoas})

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
# 5. QUẢN TRỊ ADMIN (LỚP HỌC & CHỨNG CHỈ)
# ==========================================
@login_required
def class_list(request):
    if not request.user.is_staff: return redirect('students:home')
    classes = LopBoiDuong.objects.all().order_by('-id')
    return render(request, 'admin_mofi/pages/class_list.html', {'classes': classes}) 
    # ^ Đã sửa chữ classes thành pages

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

@login_required
def quick_add_diem(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(SinhVien, id=student_id)
        LichSuThi.objects.create(
            sinh_vien=student, 
            dot_thi_id=request.POST.get('dot_thi'),
            mon_thi=request.POST.get('mon_thi'),
            diem_thanh_phan_1=request.POST.get('diem_tp1') or None,
            diem_thanh_phan_2=request.POST.get('diem_tp2') or None
        )
        messages.success(request, "Đã cập nhật điểm thi.")
    return redirect('student_detail', id=student_id)

@login_required
def quick_add_chung_chi(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(SinhVien, id=student_id)
        danh_muc = get_object_or_404(DanhMucChungChi, id=request.POST.get('danh_muc_id'))
        ChungChi.objects.create(
            sinh_vien=student, danh_muc=danh_muc,
            so_hieu=request.POST.get('so_hieu'), ngay_cap=request.POST.get('ngay_cap'),
            file_minh_chung=request.FILES.get('file_minh_chung'), trang_thai='CHO'
        )
        messages.success(request, "Đã tải lên chứng chỉ mới.")
    return redirect('student_detail', id=student_id)

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
        action = request.POST.get('action')
        ghi_chu = request.POST.get('ghi_chu', '').strip()
        if action == 'approve':
            cert.trang_thai = 'DAT'
            cert.ghi_chu_xac_minh = ghi_chu or "Chứng chỉ hợp lệ."
            messages.success(request, f"Đã duyệt cho {cert.sinh_vien.ho_ten}")
        elif action == 'reject':
            cert.trang_thai = 'KHONG_DAT'
            cert.ghi_chu_xac_minh = ghi_chu or "Thông tin chưa chính xác."
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

from .forms import KhoaForm, DanhMucChungChiForm # Đảm bảo import đủ form

# ==========================================
# QUẢN LÝ KHOA (MOFI ADMIN)
# ==========================================

# 1. Hàm hiển thị danh sách Khoa
@staff_member_required
def mofi_khoa_list(request):
    query = request.GET.get('q', '')
    # Sắp xếp theo ten_khoa vì không có ma_khoa
    danh_sach_khoa = Khoa.objects.all().order_by('ten_khoa')
    
    if query:
        # Chỉ lọc theo ten_khoa
        danh_sach_khoa = danh_sach_khoa.filter(ten_khoa__icontains=query)

    return render(request, 'admin_mofi/pages/khoa_list.html', {
        'danh_sach_khoa': danh_sach_khoa,
        'query': query
    })

# 2. Hàm Thêm / Sửa Khoa (Dùng chung)
@staff_member_required
def mofi_khoa_form(request, pk=None):
    instance = get_object_or_404(Khoa, pk=pk) if pk else None
    
    if request.method == 'POST':
        form = KhoaForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật thông tin Khoa thành công!')
            return redirect('students:mofi_khoa_list') # Đã thêm students:
    else:
        form = KhoaForm(instance=instance)
    
    return render(request, 'admin_mofi/pages/khoa_form.html', {
        'form': form, 
        'instance': instance
    })

# ==========================================
# QUẢN LÝ CHỨNG CHỈ (MOFI ADMIN)
# ==========================================

# 1. Hàm hiển thị danh sách Chứng chỉ
@staff_member_required
def mofi_chungchi_list(request):
    query = request.GET.get('q', '')
    danh_sach = DanhMucChungChi.objects.all().order_by('-id')
    
    if query:
        danh_sach = danh_sach.filter(
            # Sửa lỗi: Thay loai_chung_chi thành loai để khớp với models.py
            Q(ten_chung_chi__icontains=query) | Q(loai__icontains=query)
        )

    return render(request, 'admin_mofi/pages/chungchi_list.html', {
        'danh_sach': danh_sach,
        'query': query
    })

# 2. Hàm Thêm / Sửa Chứng chỉ dùng chung
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
    
    return render(request, 'admin_mofi/pages/chungchi_form.html', {
        'form': form, 
        'instance': instance
    })

# Nhớ đảm bảo đã import các model từ CMS ở đầu file views.py của students


@login_required
def dashboard(request):
    try:
        # 1. Lấy thông tin sinh viên dựa trên tài khoản đang đăng nhập
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
        
        # 2. Lấy dữ liệu Slider & QuickLink từ app CMS (Khối thống nhất)
        sliders = Slider.objects.filter(is_active=True).order_by('order')
        quick_links = QuickLink.objects.filter(is_active=True).order_by('order')
        
        # 3. Lấy danh sách lớp đã đăng ký của sinh viên này
        ds_dang_ky = DangKyLop.objects.filter(sinh_vien=sinh_vien).order_by('-thoi_gian_dk')
        
        # 4. Các dữ liệu phụ trợ khác cho form cập nhật hoặc hiển thị
        khoas = Khoa.objects.all().order_by('ten_khoa')
        danh_muc_cc = DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi')

        return render(request, 'students/dashboard.html', {
            'sinh_vien': sinh_vien, 
            'ds_dang_ky': ds_dang_ky,
            'khoas': khoas,
            'danh_muc_cc': danh_muc_cc,
            'sliders': sliders,       # Đẩy dữ liệu slider sang HTML
            'quick_links': quick_links # Đẩy dữ liệu quicklink sang HTML
        })
    except SinhVien.DoesNotExist:
        messages.error(request, "Hồ sơ cá nhân chưa được khởi tạo trên hệ thống.")
        return redirect('students:home')



# ==========================================
# QUẢN LÝ TÀI KHOẢN HỆ THỐNG
# ==========================================
@staff_member_required
def mofi_user_list(request):
    # Lấy danh sách user, ngoại trừ các tài khoản superuser tối cao (nếu muốn bảo mật)
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
                # NẾU LÀ TẠO MỚI: Set mật khẩu mặc định và cho phép truy cập admin (is_staff)
                user.set_password('Humg@123456') 
                user.is_staff = True
            user.save()
            form.save_m2m() # Lưu các nhóm quyền (groups)
            
            messages.success(request, 'Cập nhật tài khoản thành công!')
            return redirect('students:mofi_user_list')
    else:
        form = UserAccountForm(instance=instance)
        
    return render(request, 'admin_mofi/system/user_form.html', {
        'form': form, 
        'instance': instance
    })

# ==========================================
# QUẢN LÝ NHÓM QUYỀN (ROLES)
# ==========================================
@staff_member_required
def mofi_group_list(request):
    groups = Group.objects.all()
    return render(request, 'admin_mofi/system/group_list.html', {'groups': groups})

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
        
    return render(request, 'admin_mofi/system/group_form.html', {
        'form': form, 
        'instance': instance
    })

# --- XÓA TÀI KHOẢN, NHÓM QUYỀN, KHOA, DANH MỤC CHỨNG CHỈ ---
@staff_member_required
def mofi_user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.is_superuser:
        messages.error(request, 'Cảnh báo: Không thể xóa tài khoản SuperAdmin tối cao!')
    else:
        user.delete()
        messages.success(request, 'Đã xóa tài khoản Cán bộ thành công.')
    return redirect('students:mofi_user_list')

@staff_member_required
def mofi_group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group.delete()
    messages.success(request, 'Đã xóa Nhóm quyền thành công.')
    return redirect('students:mofi_group_list')

@staff_member_required
def mofi_khoa_delete(request, pk):
    khoa = get_object_or_404(Khoa, pk=pk)
    khoa.delete()
    messages.success(request, 'Đã xóa Khoa thành công.')
    return redirect('students:mofi_khoa_list')

@staff_member_required
def mofi_chungchi_danhmuc_delete(request, pk):
    dm = get_object_or_404(DanhMucChungChi, pk=pk)
    dm.delete()
    messages.success(request, 'Đã xóa Danh mục Chứng chỉ thành công.')
    return redirect('students:mofi_chungchi_list')

import pandas as pd
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import SinhVien, DotThi, LichSuThi
from django.contrib.admin.views.decorators import staff_member_required

# Hàm tiện ích để chuẩn hóa chuỗi tìm kiếm cột
def clean_col(s):
    return str(s).lower().strip()

@staff_member_required
def mofi_import_exam_data(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        file_type = request.POST.get('file_type') # 'LICH' hoặc 'DIEM'
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file:
            messages.error(request, "Vui lòng chọn file Excel.")
            return redirect(request.path)
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            # 1. Đọc file không header để dò dòng tiêu đề
            df_raw = pd.read_excel(excel_file, header=None)
            header_row = 0
            for i, row in df_raw.iterrows():
                row_vals = [clean_col(v) for v in row.values]
                if 'mã sinh viên' in row_vals or 'mssv' in row_vals:
                    header_row = i
                    break
            
            # 2. Đọc lại file với header chuẩn
            df = pd.read_excel(excel_file, header=header_row)
            df.columns = [clean_col(c) for c in df.columns]
            
            count = 0
            for _, row in df.iterrows():
                # Tìm cột MSSV
                mssv_key = next((c for c in df.columns if 'mã' in c and 'sinh viên' in c or 'mssv' in c), None)
                if not mssv_key or pd.isna(row[mssv_key]): continue
                
                mssv = str(row[mssv_key]).split('.')[0].strip() # Xử lý mssv bị biến thành float
                
                try:
                    sv = SinhVien.objects.get(mssv=mssv)
                except SinhVien.DoesNotExist: continue

                # Xác định môn thi dựa trên loại đợt thi
                mon_thi = "Công nghệ thông tin" if dot_thi.loai == 'TIN_HOC' else "Ngoại ngữ"

                defaults = {}
                if file_type == 'LICH':
                    # Dò các cột lịch thi
                    col_ngay = next((c for c in df.columns if 'ngày' in c), None)
                    col_ca = next((c for c in df.columns if 'ca' in c), None)
                    col_phong = next((c for c in df.columns if 'phòng' in c), None)
                    col_sbd = next((c for c in df.columns if 'sbd' in c or 'báo danh' in c), None)
                    
                    if col_ca: defaults['ca_thi'] = str(row[col_ca])
                    if col_phong: defaults['phong_thi'] = str(row[col_phong])
                    if col_sbd: defaults['sbd'] = str(row[col_sbd])
                
                else: # Import ĐIỂM
                    if dot_thi.loai == 'TIN_HOC':
                        # Lấy điểm Trắc nghiệm & Thực hành
                        c_tn = next((c for c in df.columns if 'trắc nghiệm' in c), None)
                        c_th = next((c for c in df.columns if 'thực hành' in c), None)
                        if c_tn: defaults['diem_thanh_phan_1'] = row[c_tn]
                        if c_th: defaults['diem_thanh_phan_2'] = row[c_th]
                    else:
                        # Lấy điểm Ngoại ngữ (thường là cột Điểm đánh giá)
                        c_tong = next((c for c in df.columns if 'đánh giá' in c or 'tổng' in c), None)
                        c_xl = next((c for c in df.columns if 'xếp loại' in c or 'kết quả' in c), None)
                        if c_tong: defaults['diem_thanh_phan_1'] = row[c_tong]
                        if c_xl: defaults['ghi_chu'] = str(row[c_xl])

                LichSuThi.objects.update_or_create(
                    sinh_vien=sv, dot_thi=dot_thi, mon_thi=mon_thi,
                    defaults=defaults
                )
                count += 1
            
            messages.success(request, f"Thành công! Đã cập nhật dữ liệu cho {count} sinh viên.")
            
        except Exception as e:
            messages.error(request, f"Lỗi xử lý file: {str(e)}")
            
    return redirect('students:mofi_dot_thi_list')

import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from .models import DotThi, SinhVien, LichSuThi

@staff_member_required
def mofi_import_lich_thi(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và file Excel.")
            return redirect('students:mofi_import_lich_thi')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            # 1. Đọc file để tự động tìm dòng tiêu đề chứa chữ "Mã sinh viên"
            df_raw = pd.read_excel(excel_file, header=None)
            header_row = 0
            for i, row in df_raw.iterrows():
                row_str = ' '.join([str(v).lower() for v in row.values])
                if 'mã sinh viên' in row_str or 'mssv' in row_str:
                    header_row = i
                    break
            
            # 2. Đọc dữ liệu chính thức từ dòng Header đã tìm thấy
            df = pd.read_excel(excel_file, header=header_row)
            # Chuyển tên cột về chữ thường để dễ tìm
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            count = 0
            for _, row in df.iterrows():
                # Tìm cột MSSV
                mssv_col = next((c for c in df.columns if 'mã' in c and 'sinh viên' in c or 'mssv' in c), None)
                if not mssv_col or pd.isna(row[mssv_col]): continue
                
                # Cắt đuôi .0 nếu Excel tự convert mã sinh viên thành số thập phân
                mssv = str(row[mssv_col]).split('.')[0].strip()
                
                try:
                    sv = SinhVien.objects.get(mssv=mssv)
                except SinhVien.DoesNotExist:
                    continue # Bỏ qua nếu sinh viên không có trên CRM
                    
                # Tìm linh hoạt các cột Ca, Phòng, SBD
                ca_col = next((c for c in df.columns if 'ca' in c), None)
                phong_col = next((c for c in df.columns if 'phòng' in c), None)
                sbd_col = next((c for c in df.columns if 'sbd' in c or 'báo danh' in c), None)
                
                ca_thi = str(row[ca_col]).strip() if ca_col and pd.notna(row[ca_col]) else ""
                phong_thi = str(row[phong_col]).strip() if phong_col and pd.notna(row[phong_col]) else ""
                sbd = str(row[sbd_col]).strip() if sbd_col and pd.notna(row[sbd_col]) else ""
                
                # Loại môn thi phụ thuộc vào cấu hình Đợt thi lúc Admin tạo
                mon_thi = "Công nghệ thông tin" if dot_thi.loai == 'TIN_HOC' else "Ngoại ngữ"
                
                # Cập nhật hoặc thêm mới thông tin lịch thi cho sinh viên
                LichSuThi.objects.update_or_create(
                    sinh_vien=sv, 
                    dot_thi=dot_thi, 
                    mon_thi=mon_thi,
                    defaults={
                        'ca_thi': ca_thi,
                        'phong_thi': phong_thi,
                        'sbd': sbd
                    }
                )
                count += 1
                
            messages.success(request, f"Đã đồng bộ Lịch thi & Phòng thi thành công cho {count} sinh viên.")
            return redirect('students:mofi_dot_thi_list')
            
        except Exception as e:
            messages.error(request, f"Lỗi xử lý file Excel: {str(e)}")
            
    # Lấy danh sách đợt thi để đưa vào dropdown
    dot_this = DotThi.objects.all().order_by('-ngay_thi')
    return render(request, 'admin_mofi/exams/import_lich_thi.html', {'dot_this': dot_this})

@staff_member_required
def mofi_sua_diem_thi(request, lich_thi_id):
    if request.method == 'POST':
        lt = get_object_or_404(LichSuThi, id=lich_thi_id)
        diem1 = request.POST.get('diem_thanh_phan_1')
        diem2 = request.POST.get('diem_thanh_phan_2')
        ghi_chu = request.POST.get('ghi_chu', '').strip()
        
        if diem1: lt.diem_thanh_phan_1 = float(diem1)
        if diem2: lt.diem_thanh_phan_2 = float(diem2)
        lt.ghi_chu = ghi_chu
        
        lt.save()
        messages.success(request, f"Đã cập nhật điểm thành công cho SV: {lt.sinh_vien.mssv}")
        return redirect('students:mofi_dot_thi_detail', dot_thi_id=lt.dot_thi.id)
    

import io
from django.http import HttpResponse

# ==========================================
# CÁC HÀM BỔ SUNG CHO GIAO DIỆN ADMIN MOFI
# (Dán toàn bộ phần này xuống dưới cùng của file views.py)
# ==========================================

@staff_member_required
def mofi_dot_thi_list(request):
    # Đã sử dụng đúng trường thoi_gian_bat_dau theo CSDL của bạn
    dot_this = DotThi.objects.all().order_by('-thoi_gian_bat_dau')
    return render(request, 'admin_mofi/pages/dot_thi_list.html', {'dot_this': dot_this})

@staff_member_required
def mofi_dot_thi_detail(request, dot_thi_id):
    dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
    lich_thi_list = LichSuThi.objects.filter(dot_thi=dot_thi).select_related('sinh_vien')
    return render(request, 'admin_mofi/pages/dot_thi_detail.html', {
        'dot_thi': dot_thi, 
        'lich_thi_list': lich_thi_list
    })

@staff_member_required
def mofi_sua_diem_thi(request, lich_thi_id):
    if request.method == 'POST':
        lt = get_object_or_404(LichSuThi, id=lich_thi_id)
        diem1 = request.POST.get('diem_thanh_phan_1')
        diem2 = request.POST.get('diem_thanh_phan_2')
        ghi_chu = request.POST.get('ghi_chu', '').strip()
        
        if diem1: lt.diem_thanh_phan_1 = float(diem1)
        if diem2: lt.diem_thanh_phan_2 = float(diem2)
        lt.ghi_chu = ghi_chu
        
        lt.save()
        messages.success(request, f"Đã cập nhật điểm thành công cho SV: {lt.sinh_vien.mssv}")
        return redirect('students:mofi_dot_thi_detail', dot_thi_id=lt.dot_thi.id)
    return redirect('students:mofi_dot_thi_list')

@staff_member_required
def mofi_export_bang_diem(request, dot_thi_id):
    dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
    lich_thi_list = LichSuThi.objects.filter(dot_thi=dot_thi).select_related('sinh_vien').order_by('sbd')
    
    data = []
    for lt in lich_thi_list:
        data.append({
            'MSSV': lt.sinh_vien.mssv,
            'Họ và tên': lt.sinh_vien.ho_ten,
            'Lớp': lt.sinh_vien.lop if lt.sinh_vien.lop else '',
            'Ca thi': lt.ca_thi if lt.ca_thi else '',
            'Phòng thi': lt.phong_thi if lt.phong_thi else '',
            'SBD': lt.sbd if lt.sbd else '',
            'Điểm TP1': lt.diem_thanh_phan_1 if lt.diem_thanh_phan_1 is not None else '',
            'Điểm TP2': lt.diem_thanh_phan_2 if lt.diem_thanh_phan_2 is not None else '',
            'Ghi chú': lt.ghi_chu if lt.ghi_chu else ''
        })
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='BangDiem', index=False)
        
        # Căn chỉnh độ rộng cột Excel
        worksheet = writer.sheets['BangDiem']
        for column_cells in worksheet.columns:
            length = max(len(str(cell.value)) for cell in column_cells)
            worksheet.column_dimensions[column_cells[0].column_letter].width = length + 2

    output.seek(0)
    response = HttpResponse(
        output.read(), 
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    safe_filename = str(dot_thi.ten_dot).replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="Bang_Diem_{safe_filename}.xlsx"'
    return response

@staff_member_required
def mofi_import_class_list(request):
    if request.method == 'POST':
        lop_id = request.POST.get('lop_id')
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file or not lop_id:
            messages.error(request, "Vui lòng chọn lớp học và file Excel.")
            return redirect('students:mofi_import_class_list')
            
        lop_hoc = get_object_or_404(LopBoiDuong, id=lop_id)
        try:
            df_raw = pd.read_excel(excel_file, header=None)
            header_row = 0
            for i, row in df_raw.iterrows():
                row_vals = [str(v).lower().strip() for v in row.values]
                if 'mã sinh viên' in row_vals or 'mssv' in row_vals:
                    header_row = i
                    break
            
            df = pd.read_excel(excel_file, header=header_row)
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            count = 0
            for _, row in df.iterrows():
                mssv_key = next((c for c in df.columns if 'mã' in c and 'sinh viên' in c or 'mssv' in c), None)
                if not mssv_key or pd.isna(row[mssv_key]): continue
                
                mssv = str(row[mssv_key]).split('.')[0].strip()
                try:
                    sv = SinhVien.objects.get(mssv=mssv)
                    DangKyLop.objects.update_or_create(
                        sinh_vien=sv, 
                        lop_hoc=lop_hoc,
                        defaults={'trang_thai': 'THANH_CONG'}
                    )
                    count += 1
                except SinhVien.DoesNotExist:
                    continue
            
            messages.success(request, f"Đã thêm thành công {count} sinh viên vào lớp {lop_hoc.ten_lop}!")
            return redirect('students:class_list')
            
        except Exception as e:
            messages.error(request, f"Lỗi xử lý file Excel: {str(e)}")
            
    lops = LopBoiDuong.objects.filter(trang_thai=True).order_by('-id')
    return render(request, 'admin_mofi/pages/import_class_list.html', {'lops': lops})