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
        khoa_id = request.POST.get('khoa')
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
    # BỔ SUNG DÒNG NÀY:
    danh_muc_cc = DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi')
    # NHỚ THÊM VÀO CONTEXT Ở RETURN:
    return render(request, 'admin_mofi/students/student_form.html', {'khoas': khoas, 'danh_muc_cc': danh_muc_cc})


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
    # BỔ SUNG DÒNG NÀY:
    danh_muc_cc = DanhMucChungChi.objects.all().order_by('loai', 'ten_chung_chi')
    # NHỚ THÊM VÀO CONTEXT Ở RETURN:
    return render(request, 'admin_mofi/students/student_form.html', {'student': student, 'khoas': khoas, 'danh_muc_cc': danh_muc_cc})
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
    # BỔ SUNG THÊM students: VÀO ĐÂY
    return redirect('students:student_detail', id=student_id) 

# Hãy chắc chắn bạn đã có dòng này ở tít trên cùng của file views.py nhé:
from django.db import IntegrityError

@login_required
def quick_add_chung_chi(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(SinhVien, id=student_id)
        danh_muc = get_object_or_404(DanhMucChungChi, id=request.POST.get('danh_muc_id'))
        so_hieu_nhap = request.POST.get('so_hieu').strip() # Xóa khoảng trắng thừa
        
        try:
            ChungChi.objects.create(
                sinh_vien=student, danh_muc=danh_muc,
                so_hieu=so_hieu_nhap, ngay_cap=request.POST.get('ngay_cap'),
                file_minh_chung=request.FILES.get('file_minh_chung'), trang_thai='CHO'
            )
            messages.success(request, "Đã tải lên chứng chỉ mới thành công.")
            
        except IntegrityError:
            # BẮT LỖI: Nếu Database báo trùng số hiệu
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
            # 1. Định vị dòng Tiêu đề
            df_raw = pd.read_excel(excel_file, header=None)
            header_row = 0
            for i, row in df_raw.iterrows():
                row_vals = [str(v).lower().strip() for v in row.values]
                if any(k in v for v in row_vals for k in ['mã sinh viên', 'mssv']):
                    header_row = i
                    break
            
            df = pd.read_excel(excel_file, header=header_row)
            df.columns = [str(c).lower().strip() for c in df.columns]
            headers_str = " ".join(df.columns)
            
            # 2. VALIDATION GUARD: Bắt lỗi up nhầm file
            if 'trắc nghiệm' not in headers_str and 'thực hành' not in headers_str:
                messages.error(request, "❌ CẢNH BÁO: File không đúng chuẩn Tin học! Bắt buộc phải có cột 'Trắc nghiệm' hoặc 'Thực hành'.")
                return redirect('students:mofi_import_diem_cntt')
            
            count_new_sv = 0
            count_update_diem = 0
            
            # 3. Mở luồng xử lý tốc độ cao (Transaction)
            with transaction.atomic():
                for _, row in df.iterrows():
                    c_mssv = next((c for c in df.columns if 'mã sinh viên' in c or 'mssv' in c), None)
                    if not c_mssv or pd.isna(row[c_mssv]): continue
                    mssv = str(row[c_mssv]).split('.')[0].strip()
                    if not mssv: continue
                    
                    # Lấy Họ và tên
                    c_hoten = next((c for c in df.columns if 'họ và tên' in c or 'họ tên' in c), None)
                    ho_ten_full = str(row[c_hoten]).strip() if c_hoten and pd.notna(row[c_hoten]) else f"SV_{mssv}"

                    # Tạo Tài khoản & Hồ sơ tự động
                    user, u_created = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                    if u_created:
                        user.set_password('cfihumg')
                        user.save()
                    
                    sv, sv_created = SinhVien.objects.get_or_create(
                        mssv=mssv, defaults={'user': user, 'ho_ten': ho_ten_full}
                    )
                    if sv_created: count_new_sv += 1

                    # Bóc tách điểm Tin học
                    def get_val(keys):
                        col = next((c for c in df.columns if any(k in c for k in keys)), None)
                        return pd.to_numeric(row[col], errors='coerce') if col and pd.notna(row[col]) else None

                    # Trắc nghiệm (Module 1) và Thực hành (Module 2)
                    defaults = {
                        'diem_thanh_phan_1': get_val(['trắc nghiệm', 'lý thuyết']),
                        'diem_thanh_phan_2': get_val(['thực hành']),
                        'diem_tong': get_val(['điểm đánh giá', 'tổng']),
                    }
                    
                    c_xl = next((c for c in df.columns if 'xếp loại' in c or 'kết quả' in c), None)
                    c_gc = next((c for c in df.columns if 'ghi chú' in c), None)
                    if c_xl and pd.notna(row[c_xl]): defaults['xep_loai'] = str(row[c_xl]).strip()
                    if c_gc and pd.notna(row[c_gc]): defaults['ghi_chu'] = str(row[c_gc]).strip()

                    LichSuThi.objects.update_or_create(
                        sinh_vien=sv, dot_thi=dot_thi, defaults=defaults
                    )
                    count_update_diem += 1

            messages.success(request, f"✅ Đã nạp thành công Điểm CĐR TIN HỌC! (Tạo mới {count_new_sv} hồ sơ | Cập nhật {count_update_diem} sinh viên).")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
            
        except Exception as e:
            messages.error(request, f"❌ Lỗi xử lý file Excel: {str(e)}")
            
    # Lọc danh sách đợt thi
    dot_this = DotThi.objects.all().order_by('-id')
    return render(request, 'admin_mofi/pages/import_diem_cntt.html', {'dot_this': dot_this})

import pandas as pd
from django.db import transaction
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import SinhVien, DotThi, LichSuThi
from django.db import transaction, connection

@staff_member_required
def mofi_import_diem_tdnn(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        connection.close()

        try:
            # 1. Tìm dòng header
            df_raw = pd.read_excel(excel_file, header=None)
            header_idx = next((i for i, row in df_raw.iterrows() if any('mã sinh viên' in str(v).lower() for v in row.values)), 0)
            
            df = pd.read_excel(excel_file, header=header_idx)
            df.columns = [str(c).lower().strip() for c in df.columns]

            # 2. TỐI ƯU HÓA: KÉO DỮ LIỆU CŨ LÊN RAM ĐỂ ĐỐI CHIẾU
            c_mssv = next((c for c in df.columns if 'mã sinh viên' in c or 'mssv' in c), None)
            if not c_mssv:
                raise Exception("Không tìm thấy cột Mã sinh viên trong file.")

            # Lấy danh sách MSSV từ Excel
            mssv_list = df[c_mssv].dropna().astype(str).str.split('.').str[0].str.strip().tolist()
            
            # Đưa toàn bộ Sinh Viên và User vào RAM dưới dạng Từ điển (Dictionary)
            users_dict = {u.username: u for u in User.objects.filter(username__in=mssv_list)}
            sv_dict = {sv.mssv: sv for sv in SinhVien.objects.filter(mssv__in=mssv_list)}

            lich_su_thi_objects = []
            d_chuan = dot_thi.diem_chuan_ngoai_ngu
            d_liet = dot_thi.diem_liet_ngoai_ngu

            with transaction.atomic():
                # XÓA ĐIỂM CŨ CỦA ĐỢT NÀY ĐỂ TRÁNH TRÙNG LẶP KHI NẠP LẠI NHIỀU LẦN
                LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi='TA_DAU_VAO').delete()

                for index, row in df.iterrows():
                    mssv = str(row[c_mssv]).split('.')[0].strip()
                    if not mssv or mssv == 'nan': continue

                    # ---- ĐỒNG BỘ SINH VIÊN SIÊU TỐC ----
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

                    # ---- LẤY ĐIỂM VÀ TÍNH TOÁN TRONG RAM ----
                    def get_d(key):
                        col = next((c for c in df.columns if key in c), None)
                        return pd.to_numeric(row[col], errors='coerce') if col else None

                    nghe = get_d('nghe')
                    doc = get_d('đọc')
                    viet = get_d('viết')
                    noi = get_d('nói')
                    xep_loai = str(row.get('xếp loại', '')).replace('nan', '').strip()
                    ghi_chu = str(row.get('ghi chú', '')).replace('nan', '').strip()

                    # Tính tổng điểm
                    valid_diems = [d for d in [nghe, doc, viet, noi] if pd.notna(d)]
                    diem_tong = round(sum(valid_diems), 2) if valid_diems else 0

                    # Xét Đạt/Trượt ngay trên RAM
                    is_pass = False
                    xl_lower = xep_loai.lower()
                    gc_lower = ghi_chu.lower()

                    if any(k in xl_lower or k in gc_lower for k in ['vắng', 'bỏ thi', 'đình chỉ', 'không đạt']):
                        is_pass = False
                    elif any(k in xl_lower for k in ['đủ điều kiện', 'đạt', 'pass', 'b1', 'b2', 'a2', 'c1']):
                        is_pass = True
                    else:
                        bi_liet = any(d <= d_liet for d in valid_diems) if d_liet >= 0 else False
                        if not bi_liet and diem_tong >= d_chuan:
                            is_pass = True

                    # TẠO GÓI HÀNG (Chưa gửi vào Database)
                    lst = LichSuThi(
                        sinh_vien=sv,
                        dot_thi=dot_thi,
                        mon_thi='TA_DAU_VAO',
                        diem_thanh_phan_1=nghe,
                        diem_thanh_phan_2=doc,
                        diem_thanh_phan_3=viet,
                        diem_thanh_phan_4=noi,
                        diem_tong=diem_tong,
                        xep_loai=xep_loai,
                        ghi_chu=ghi_chu,
                        ket_qua_dat=is_pass
                    )
                    lich_su_thi_objects.append(lst)

                # 3. GỬI 1.139 BẢN GHI VÀO DATABASE BẰNG 1 LỆNH DUY NHẤT (BULK CREATE)
                LichSuThi.objects.bulk_create(lich_su_thi_objects, batch_size=500)

            messages.success(request, f"Đã nạp siêu tốc {len(lich_su_thi_objects)} bản ghi điểm thi!")
        except Exception as e:
            messages.error(request, f"Lỗi xử lý file: {str(e)}")
        
        return redirect('students:mofi_import_diem_tdnn')

    return render(request, 'admin_mofi/pages/import_diem_tdnn.html', {'dot_this': DotThi.objects.all().order_by('-id')})

@staff_member_required
def mofi_import_diem_cdr_nn(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và tải lên file Excel.")
            return redirect('students:mofi_import_diem_cdr_nn')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            # 1. Tìm dòng Tiêu đề
            df_raw = pd.read_excel(excel_file, header=None)
            header_row = 0
            for i, row in df_raw.iterrows():
                row_vals = [str(v).lower().strip() for v in row.values]
                if any(k in v for v in row_vals for k in ['mã sinh viên', 'mssv']):
                    header_row = i
                    break
            
            df = pd.read_excel(excel_file, header=header_row)
            df.columns = [str(c).lower().strip() for c in df.columns]
            headers_str = " ".join(df.columns)
            
            # 2. VALIDATION GUARD: Bắt lỗi up nhầm file
            if not all(k in headers_str for k in ['nghe', 'đọc', 'viết', 'nói']):
                messages.error(request, "❌ CẢNH BÁO: File không đúng chuẩn CĐR Ngoại Ngữ! Bắt buộc phải có đủ 4 cột 'Nghe', 'Đọc', 'Viết', 'Nói'.")
                return redirect('students:mofi_import_diem_cdr_nn')
            
            count_new_sv = 0
            count_update_diem = 0
            
            # 3. Bắt đầu Import tốc độ cao
            with transaction.atomic():
                for _, row in df.iterrows():
                    c_mssv = next((c for c in df.columns if 'mã sinh viên' in c or 'mssv' in c), None)
                    if not c_mssv or pd.isna(row[c_mssv]): continue
                    mssv = str(row[c_mssv]).split('.')[0].strip()
                    if not mssv: continue
                    
                    # Ghép Họ và Tên
                    c_ho = next((c for c in df.columns if 'họ' in c), None)
                    c_ten = next((c for c in df.columns if 'tên' in c and 'họ' not in c), None)
                    ho_ten = f"{row[c_ho] if c_ho else ''} {row[c_ten] if c_ten else ''}".strip() or f"SV_{mssv}"

                    # Tự động cấp Tài khoản
                    user, u_created = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                    if u_created:
                        user.set_password('cfihumg')
                        user.save()
                    
                    # Tự động tạo Hồ sơ
                    sv, sv_created = SinhVien.objects.get_or_create(
                        mssv=mssv, defaults={'user': user, 'ho_ten': ho_ten}
                    )
                    if sv_created: count_new_sv += 1

                    # Bóc tách điểm 4 kỹ năng CĐR
                    def get_score(key):
                        col = next((c for c in df.columns if key in c), None)
                        return pd.to_numeric(row[col], errors='coerce') if col else None

                    defaults = {
                        'diem_thanh_phan_1': get_score('nghe'),
                        'diem_thanh_phan_2': get_score('đọc'),
                        'diem_thanh_phan_3': get_score('viết'),
                        'diem_thanh_phan_4': get_score('nói'),
                        'diem_tong': get_score('điểm đánh giá') or get_score('tổng') or get_score('phương án'),
                    }
                    
                    # Lấy Xếp loại, Ghi chú và Bảo lưu (nếu có)
                    c_xl = next((c for c in df.columns if 'xếp loại' in c or 'kết quả' in c), None)
                    c_gc = next((c for c in df.columns if 'ghi chú' in c), None)
                    
                    if c_xl and pd.notna(row[c_xl]): defaults['xep_loai'] = str(row[c_xl]).strip()
                    if c_gc and pd.notna(row[c_gc]): defaults['ghi_chu'] = str(row[c_gc]).strip()

                    LichSuThi.objects.update_or_create(
                        sinh_vien=sv, dot_thi=dot_thi, defaults=defaults
                    )
                    count_update_diem += 1

            messages.success(request, f"✅ Nạp CĐR NGOẠI NGỮ thành công! Tạo mới {count_new_sv} hồ sơ | Cập nhật điểm cho {count_update_diem} SV.")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
            
        except Exception as e:
            messages.error(request, f"❌ Lỗi xử lý file: {str(e)}")
            return redirect('students:mofi_import_diem_cdr_nn')
            
    dot_this = DotThi.objects.all().order_by('-id')
    return render(request, 'admin_mofi/pages/import_diem_cdr_nn.html', {'dot_this': dot_this})

from django.db import transaction
import pandas as pd

# --- 1. IMPORT LỊCH THI TIN HỌC (1 LỊCH) ---
@staff_member_required
def mofi_import_lich_thi_cntt(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và tải lên file.")
            return redirect('students:mofi_import_lich_thi_cntt')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            df = pd.read_excel(excel_file, header=2) # Đọc từ dòng 3 (index 2)
            df.columns = [str(c).lower().strip() for c in df.columns]

            count_new = 0
            with transaction.atomic():
                for _, row in df.iterrows():
                    c_mssv = next((c for c in df.columns if 'mssv' in c or 'mã sinh viên' in c), None)
                    if not c_mssv or pd.isna(row[c_mssv]): continue
                    mssv = str(row[c_mssv]).split('.')[0].strip()

                    # Tự động tạo Tài khoản & Hồ sơ
                    user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                    if _: 
                        user.set_password('cfihumg')
                        user.save()
                    sv, _ = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': f"SV_{mssv}"})

                    # Dò 1 lịch thi duy nhất
                    LichSuThi.objects.update_or_create(
                        sinh_vien=sv, dot_thi=dot_thi,
                        defaults={
                            'sbd': str(row.get('số báo danh', row.get('sbd', ''))),
                            'ngay_thi': str(row.get('ngày thi', row.get('ngày', ''))),
                            'ca_thi': str(row.get('ca thi', row.get('ca', ''))),
                            'phong_thi': str(row.get('phòng thi', row.get('phòng', ''))),
                        }
                    )
                    count_new += 1
            messages.success(request, f"Đã nạp Lịch thi Tin học thành công cho {count_new} sinh viên!")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e:
            messages.error(request, f"Lỗi: {e}")
            return redirect('students:mofi_import_lich_thi_cntt')
            
    return render(request, 'admin_mofi/pages/import_lich_thi_cntt.html', {'dot_this': DotThi.objects.all().order_by('-id')})


# --- 2. IMPORT LỊCH THI NGOẠI NGỮ (DÒ 2 LỊCH) ---
@staff_member_required
def mofi_import_lich_thi_nn(request):
    if request.method == 'POST':
        dot_thi_id = request.POST.get('dot_thi')
        excel_file = request.FILES.get('excel_file')
        if not excel_file or not dot_thi_id:
            messages.error(request, "Vui lòng chọn đợt thi và tải lên file.")
            return redirect('students:mofi_import_lich_thi_nn')
            
        dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
        
        try:
            df = pd.read_excel(excel_file, header=2)
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            count_new = 0
            with transaction.atomic():
                for _, row in df.iterrows():
                    c_mssv = next((c for c in df.columns if 'mssv' in c or 'mã sinh viên' in c), None)
                    if not c_mssv or pd.isna(row[c_mssv]): continue
                    mssv = str(row[c_mssv]).split('.')[0].strip()

                    user, _ = User.objects.get_or_create(username=mssv, defaults={'is_active': True})
                    if _: 
                        user.set_password('cfihumg')
                        user.save()
                    sv, _ = SinhVien.objects.get_or_create(mssv=mssv, defaults={'user': user, 'ho_ten': f"SV_{mssv}"})
                    
                    # Tìm các cột Ngày, Ca, Phòng
                    date_cols = [c for c in df.columns if 'ngày' in str(c).lower()]
                    room_cols = [c for c in df.columns if 'phòng' in str(c).lower()]
                    shift_cols = [c for c in df.columns if 'ca' in str(c).lower()]

                    defaults = {
                        'sbd': str(row.get('số báo danh', row.get('sbd', ''))),
                        # Lịch 1
                        'ngay_thi': str(row[date_cols[0]]) if len(date_cols) > 0 and pd.notna(row[date_cols[0]]) else None,
                        'phong_thi': str(row[room_cols[0]]) if len(room_cols) > 0 and pd.notna(row[room_cols[0]]) else None,
                        'ca_thi': str(row[shift_cols[0]]) if len(shift_cols) > 0 and pd.notna(row[shift_cols[0]]) else None,
                        # Lịch 2 (Nói)
                        'ngay_thi_2': str(row[date_cols[1]]) if len(date_cols) > 1 and pd.notna(row[date_cols[1]]) else None,
                        'phong_thi_2': str(row[room_cols[1]]) if len(room_cols) > 1 and pd.notna(row[room_cols[1]]) else None,
                        'ca_thi_2': str(row[shift_cols[1]]) if len(shift_cols) > 1 and pd.notna(row[shift_cols[1]]) else None,
                    }
                    LichSuThi.objects.update_or_create(sinh_vien=sv, dot_thi=dot_thi, defaults=defaults)
                    count_new += 1
                    
            messages.success(request, f"Đã nạp Lịch thi Ngoại ngữ thành công cho {count_new} sinh viên!")
            return redirect('students:mofi_dot_thi_detail', dot_thi_id=dot_thi.id)
        except Exception as e: 
            messages.error(request, f"Lỗi: {e}")
            return redirect('students:mofi_import_lich_thi_nn')
            
    return render(request, 'admin_mofi/pages/import_lich_thi_nn.html', {'dot_this': DotThi.objects.all().order_by('-id')})

from django.utils.dateparse import parse_datetime

@staff_member_required
def mofi_dot_thi_list(request):
    if request.method == 'POST':
        # Bắt dữ liệu từ Form Modal
        ma_dot = request.POST.get('ma_dot')
        ten_dot = request.POST.get('ten_dot')
        thoi_gian_bat_dau = request.POST.get('thoi_gian_bat_dau')
        thoi_gian_ket_thuc = request.POST.get('thoi_gian_ket_thuc')
        
        # Cấu hình điểm
        diem_chuan_nn = request.POST.get('diem_chuan_ngoai_ngu', 5.0)
        diem_liet_nn = request.POST.get('diem_liet_ngoai_ngu', 0.0)
        diem_chuan_th = request.POST.get('diem_chuan_tin_hoc', 5.0)
        diem_liet_th = request.POST.get('diem_liet_tin_hoc', 0.0)
        
        file_tb = request.FILES.get('file_thong_bao')
        trang_thai = request.POST.get('trang_thai') == 'on' # Checkbox

        try:
            DotThi.objects.create(
                ma_dot=ma_dot,
                ten_dot=ten_dot,
                thoi_gian_bat_dau=parse_datetime(thoi_gian_bat_dau) if thoi_gian_bat_dau else timezone.now(),
                thoi_gian_ket_thuc=parse_datetime(thoi_gian_ket_thuc) if thoi_gian_ket_thuc else timezone.now(),
                diem_chuan_ngoai_ngu=float(diem_chuan_nn),
                diem_liet_ngoai_ngu=float(diem_liet_nn),
                diem_chuan_tin_hoc=float(diem_chuan_th),
                diem_liet_tin_hoc=float(diem_liet_th),
                file_thong_bao=file_tb,
                trang_thai=trang_thai
            )
            messages.success(request, f"Tạo thành công đợt thi: {ten_dot}")
        except Exception as e:
            messages.error(request, f"Lỗi tạo đợt thi: Kiểm tra xem Mã đợt đã tồn tại chưa. ({str(e)})")
        
        return redirect('students:mofi_dot_thi_list')

    # Hiển thị danh sách bình thường
    dot_this = DotThi.objects.all().order_by('-id')
    return render(request, 'admin_mofi/pages/dot_thi_list.html', {'dot_this': dot_this})

from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from .models import DotThi, LichSuThi
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def mofi_dot_thi_detail(request, dot_thi_id):
    # Lấy thông tin đợt thi
    dot_thi = get_object_or_404(DotThi, id=dot_thi_id)
    
    # 1. LẤY THAM SỐ TỪ URL (Tìm kiếm, Sắp xếp, Tab)
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '-ngay_cap_nhat') # Mặc định bản ghi mới lên đầu
    active_tab = request.GET.get('tab', 'tdnn')

    # 2. HÀM TRÍCH XUẤT, LỌC & SẮP XẾP CHUNG
    def get_filtered_qs(mon_thi_code):
        # select_related để chống lỗi N+1 Query
        qs = LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi=mon_thi_code).select_related('sinh_vien')
        
        # Nếu người dùng có nhập ô tìm kiếm
        if search_query:
            qs = qs.filter(
                Q(sinh_vien__mssv__icontains=search_query) | 
                Q(sinh_vien__ho_ten__icontains=search_query)
            )
            
        return qs.order_by(sort_by)

    # Lấy 3 luồng dữ liệu (đã áp dụng Tìm kiếm & Sắp xếp)
    qs_tdnn = get_filtered_qs('TA_DAU_VAO')
    qs_cdr_nn = get_filtered_qs('CDR_NGOAI_NGU')
    qs_cdr_tin = get_filtered_qs('CDR_TIN_HOC')

    # 3. HÀM TÍNH THỐNG KÊ TỔNG QUAN
    # Tối ưu BA: Tính trên dữ liệu GỐC để bảng thống kê không bị teo nhỏ khi gõ Tìm kiếm
    def get_stats(mon_thi_code):
        qs_base = LichSuThi.objects.filter(dot_thi=dot_thi, mon_thi=mon_thi_code)
        total = qs_base.count()
        passed = qs_base.filter(ket_qua_dat=True).count()
        failed = total - passed
        rate = round((passed / total * 100), 1) if total > 0 else 0
        return {'total': total, 'passed': passed, 'failed': failed, 'rate': rate}

    stats = {
        'tdnn': get_stats('TA_DAU_VAO'),
        'cdr_nn': get_stats('CDR_NGOAI_NGU'),
        'cdr_tin': get_stats('CDR_TIN_HOC')
    }

    # 4. PHÂN TRANG (50 dòng mỗi trang)
    page_tdnn = Paginator(qs_tdnn, 50).get_page(request.GET.get('p_tdnn', 1))
    page_cdr_nn = Paginator(qs_cdr_nn, 50).get_page(request.GET.get('p_cdr_nn', 1))
    page_cdr_tin = Paginator(qs_cdr_tin, 50).get_page(request.GET.get('p_cdr_tin', 1))

    # 5. ĐÓNG GÓI RA GIAO DIỆN
    context = {
        'dot_thi': dot_thi,
        'stats': stats,
        'page_tdnn': page_tdnn,
        'page_cdr_nn': page_cdr_nn,
        'page_cdr_tin': page_cdr_tin,
        'active_tab': active_tab,
        'search_query': search_query, # Truyền ra để giữ chữ trong ô input HTML
        'sort_by': sort_by            # Truyền ra để xử lý highlight nút Sắp xếp
    }
    return render(request, 'admin_mofi/pages/dot_thi_detail.html', context)