import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q

# Import Models từ cả 2 app
from cms.models import Post, Category 
from .models import SinhVien, LopBoiDuong, DangKyLop, LichSuThi


# ==========================================
# 1. TRANG CHỦ & TRA CỨU (Giữ nguyên)
# ==========================================
def home(request):
    slider_posts = Post.objects.filter(is_published=True).order_by('-created_at')[:3]
    news_category = Category.objects.filter(slug__icontains='tin').first()
    news_posts = Post.objects.filter(is_published=True, category=news_category).order_by('-created_at')[:4] if news_category else []
    notice_category = Category.objects.filter(slug__icontains='thong-bao').first()
    notice_posts = Post.objects.filter(is_published=True, category=notice_category).order_by('-created_at')[:5] if notice_category else []
    dynamic_categories = Category.objects.filter(show_on_homepage=True, is_active=True)
    home_blocks = []
    for cat in dynamic_categories:
        posts = Post.objects.filter(category=cat, is_published=True).order_by('-created_at')[:4]
        home_blocks.append({'category': cat, 'posts': posts})
    
    return render(request, 'students/home.html', {
        'slider_posts': slider_posts, 'news_posts': news_posts, 'news_category': news_category,
        'notice_posts': notice_posts, 'notice_category': notice_category, 'home_blocks': home_blocks,
    })

def tra_cuu(request):
    query_mssv = request.GET.get('mssv', '').strip()
    sinh_vien, thong_bao, lich_su_thi = None, None, None
    if query_mssv:
        try:
            sinh_vien = SinhVien.objects.get(mssv=query_mssv)
            lich_su_thi = sinh_vien.lich_su_thi.all().order_by('-ngay_cap_nhat')
        except SinhVien.DoesNotExist:
            thong_bao = f"Không tìm thấy sinh viên nào với mã số: {query_mssv}"

    return render(request, 'students/tra_cuu.html', {
        'sinh_vien': sinh_vien, 'query_mssv': query_mssv, 'thong_bao': thong_bao, 'lich_su_thi': lich_su_thi
    })


# ==========================================
# 2. XÁC THỰC TÀI KHOẢN (AUTH)
# ==========================================
def dang_nhap(request):
    if request.method == 'POST':
        mssv = request.POST.get('mssv')
        mat_khau = request.POST.get('password')
        user = authenticate(request, username=mssv, password=mat_khau)
        if user is not None:
            login(request, user)
            messages.success(request, f'Xin chào {user.first_name}!')
            next_url = request.GET.get('next') 
            return redirect(next_url) if next_url else redirect('home')
        else:
            messages.error(request, 'Mã sinh viên hoặc mật khẩu không chính xác!')
    return render(request, 'students/login.html')

def dang_xuat(request):
    logout(request)
    messages.info(request, 'Bạn đã đăng xuất thành công.')
    return redirect('home')


# ==========================================
# 3. CHỨC NĂNG CỦA SINH VIÊN (PORTAL)
# ==========================================
@login_required(login_url='dang_nhap')
def danh_sach_lop(request):
    try:
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
    except SinhVien.DoesNotExist:
        messages.error(request, 'Hồ sơ sinh viên chưa tồn tại trên hệ thống. Vui lòng liên hệ Phòng Đào tạo.')
        return redirect('home')

    if request.method == 'POST':
        lop_id = request.POST.get('lop_id')
        file_minh_chung = request.FILES.get('file_minh_chung')
        if not file_minh_chung:
            messages.error(request, 'Vui lòng đính kèm ảnh biên lai/minh chứng chuyển khoản.')
            return redirect('danh_sach_lop')

        try:
            lop_hoc = LopBoiDuong.objects.get(id=lop_id, trang_thai=True)
            if DangKyLop.objects.filter(sinh_vien=sinh_vien, lop_hoc=lop_hoc).exists():
                messages.warning(request, f'Bạn đã gửi yêu cầu đăng ký lớp {lop_hoc.ten_lop} trước đó. Vui lòng chờ Cán bộ duyệt.')
            else:
                DangKyLop.objects.create(sinh_vien=sinh_vien, lop_hoc=lop_hoc, file_minh_chung=file_minh_chung)
                messages.success(request, f'Đã gửi yêu cầu đăng ký lớp {lop_hoc.ten_lop} thành công!')
        except LopBoiDuong.DoesNotExist:
            messages.error(request, 'Lớp học không tồn tại hoặc đã đóng cổng đăng ký.')
        return redirect('danh_sach_lop')

    lops = LopBoiDuong.objects.filter(trang_thai=True).order_by('-id')
    da_dang_ky_ids = DangKyLop.objects.filter(sinh_vien=sinh_vien).values_list('lop_hoc_id', flat=True)
    return render(request, 'students/danh_sach_lop.html', {'lops': lops, 'da_dang_ky_ids': da_dang_ky_ids, 'sinh_vien': sinh_vien})

@login_required(login_url='dang_nhap')
def dashboard(request):
    try:
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
        ds_dang_ky = DangKyLop.objects.filter(sinh_vien=sinh_vien).order_by('-thoi_gian_dk')
        ket_qua_thi = sinh_vien.lich_su_thi.all().order_by('-ngay_cap_nhat')[:5]
        return render(request, 'students/dashboard.html', {'sinh_vien': sinh_vien, 'ds_dang_ky': ds_dang_ky, 'ket_qua_thi': ket_qua_thi})
    except SinhVien.DoesNotExist:
        messages.error(request, "Vui lòng cập nhật hồ sơ sinh viên.")
        return redirect('home')

@login_required(login_url='dang_nhap')
def cap_nhat_ho_so(request):
    if request.method == 'POST':
        try:
            sinh_vien = SinhVien.objects.get(mssv=request.user.username)
            if request.POST.get('so_dien_thoai'): sinh_vien.so_dien_thoai = request.POST.get('so_dien_thoai')
            if request.POST.get('email_ca_nhan'): sinh_vien.email_ca_nhan = request.POST.get('email_ca_nhan')
            if request.FILES.get('anh_dai_dien'): sinh_vien.anh_dai_dien = request.FILES.get('anh_dai_dien')
            sinh_vien.save()
            messages.success(request, 'Cập nhật hồ sơ cá nhân thành công!')
        except SinhVien.DoesNotExist:
            messages.error(request, 'Lỗi cập nhật. Không tìm thấy hồ sơ.')
    return redirect('dashboard')


# ==========================================
# 4. GIAO DIỆN QUẢN TRỊ (ADMIN MOFI - HUMG CRM)
# ==========================================
def admin_mofi_dashboard(request):
    return render(request, 'admin_mofi/dashboard.html')

def import_sinh_vien(request):
    # Hàm này sau sẽ cấu hình lại giao diện theo Mofi
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Vui lòng chọn file Excel.")
            return redirect('import_sinh_vien')
        try:
            df = pd.read_excel(excel_file)
            count = 0
            for _, row in df.iterrows():
                SinhVien.objects.update_or_create(
                    mssv=str(row['MSSV']).strip(),
                    defaults={
                        'ho_ten': str(row['HoTen']).strip(),
                        'khoa': str(row.get('Khoa', '')).strip(),
                        'email_truong': str(row.get('Email', '')).strip(),
                    }
                )
                count += 1
            messages.success(request, f'Đã nhập/cập nhật {count} sinh viên.')
        except Exception as e:
            messages.error(request, f'Lỗi đọc file: {e}')
    return render(request, 'students/import_excel.html')

# --- Các hàm cho Quản lý Sinh viên (CRUD) ---
def student_list(request):
    return render(request, 'admin_mofi/students/student_list.html')

def student_add(request):
    if request.method == 'POST':
        return redirect('student_list') 
    return render(request, 'admin_mofi/students/student_form.html')

def student_edit(request, id):
    return render(request, 'admin_mofi/students/student_form.html')

def student_delete(request, id):
    return redirect('student_list')


from django.shortcuts import render
# Nhớ đảm bảo bạn đã import các Model này ở đầu file views.py nhé!
from .models import SinhVien, LopBoiDuong, DangKyLop, LichSuThi 

def admin_mofi_dashboard(request):
    # 1. Đếm tổng số sinh viên có trong DB
    total_students = SinhVien.objects.count()
    
    # 2. Đếm số lớp học đang Mở (trang_thai=True)
    active_classes = LopBoiDuong.objects.filter(trang_thai=True).count()
    
    # 3. Đếm số lượt đăng ký (Tạm đếm tổng, nếu có trường trạng thái thì dùng .filter())
    pending_registrations = DangKyLop.objects.count()
    
    # 4. Đếm số lượng chứng chỉ/lịch sử thi đã cập nhật
    certificates_issued = LichSuThi.objects.count()
    
    # 5. Lấy 5 lượt đăng ký GẦN NHẤT để hiển thị ra bảng
    # Dùng select_related để tối ưu hóa truy vấn Database (chạy cực nhanh)
    recent_activities = DangKyLop.objects.select_related('sinh_vien', 'lop_hoc').order_by('-thoi_gian_dk')[:5]

    # Đóng gói toàn bộ dữ liệu thật để gửi ra Giao diện
    context = {
        'total_students': total_students,
        'active_classes': active_classes,
        'pending_registrations': pending_registrations,
        'certificates_issued': certificates_issued,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'admin_mofi/pages/dashboard.html', context)