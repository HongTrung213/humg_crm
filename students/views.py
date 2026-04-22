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
    return render(request, 'admin_mofi/classes/class_list.html', {'classes': classes})

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