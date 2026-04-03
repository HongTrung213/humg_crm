import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q

# Import Models từ cả 2 app
from cms.models import Post, Category 
from .models import SinhVien, LopBoiDuong, DangKyLop, LichSuThi

# Các hàm phía dưới (home, tra_cuu, dang_nhap...) bạn GIỮ NGUYÊN không cần sửa gì cả!

# ==========================================
# 1. TRANG CHỦ & TRA CỨU
# ==========================================
def home(request):
    # 1. Slider
    slider_posts = Post.objects.filter(is_published=True).order_by('-created_at')[:3]
    
    # 2. Xử lý phần Tin tức (Cột trái)
    news_category = Category.objects.filter(slug__icontains='tin').first()
    news_posts = Post.objects.filter(is_published=True, category=news_category).order_by('-created_at')[:4] if news_category else []
    
    # 3. Xử lý phần Thông báo (Cột phải)
    notice_category = Category.objects.filter(slug__icontains='thong-bao').first()
    notice_posts = Post.objects.filter(is_published=True, category=notice_category).order_by('-created_at')[:5] if notice_category else []
    
    # 4. Khối danh mục động bên dưới
    dynamic_categories = Category.objects.filter(show_on_homepage=True, is_active=True)
    home_blocks = []
    for cat in dynamic_categories:
        posts = Post.objects.filter(category=cat, is_published=True).order_by('-created_at')[:4]
        home_blocks.append({
            'category': cat,
            'posts': posts
        })
    
    return render(request, 'students/home.html', {
        'slider_posts': slider_posts,
        'news_posts': news_posts,
        'news_category': news_category,
        'notice_posts': notice_posts,
        'notice_category': notice_category,
        'home_blocks': home_blocks,
    })

def tra_cuu(request):
    query_mssv = request.GET.get('mssv', '').strip()
    sinh_vien = None
    thong_bao = None
    lich_su_thi = None

    if query_mssv:
        try:
            sinh_vien = SinhVien.objects.get(mssv=query_mssv)
            lich_su_thi = sinh_vien.lich_su_thi.all().order_by('-ngay_cap_nhat')
        except SinhVien.DoesNotExist:
            thong_bao = f"Không tìm thấy sinh viên nào với mã số: {query_mssv}"

    return render(request, 'students/tra_cuu.html', {
        'sinh_vien': sinh_vien,
        'query_mssv': query_mssv,
        'thong_bao': thong_bao,
        'lich_su_thi': lich_su_thi
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
# 3. ĐĂNG KÝ LỚP HỌC (GỘP CHUNG LOGIC)
# ==========================================
@login_required(login_url='dang_nhap')
def danh_sach_lop(request):
    # 1. Lấy thông tin sinh viên dựa trên User đang đăng nhập (username chính là MSSV)
    try:
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
    except SinhVien.DoesNotExist:
        messages.error(request, 'Hồ sơ sinh viên chưa tồn tại trên hệ thống. Vui lòng liên hệ Phòng Đào tạo.')
        return redirect('home')

    # 2. XỬ LÝ KHI SINH VIÊN BẤM NÚT ĐĂNG KÝ (POST)
    if request.method == 'POST':
        lop_id = request.POST.get('lop_id')
        file_minh_chung = request.FILES.get('file_minh_chung')

        # Kiểm tra file minh chứng (bắt buộc)
        if not file_minh_chung:
            messages.error(request, 'Vui lòng đính kèm ảnh biên lai/minh chứng chuyển khoản.')
            return redirect('danh_sach_lop')

        try:
            lop_hoc = LopBoiDuong.objects.get(id=lop_id, trang_thai=True)

            # KIỂM TRA TRÙNG LẶP: Sinh viên đã đăng ký lớp này chưa?
            if DangKyLop.objects.filter(sinh_vien=sinh_vien, lop_hoc=lop_hoc).exists():
                messages.warning(request, f'Bạn đã gửi yêu cầu đăng ký lớp {lop_hoc.ten_lop} trước đó. Vui lòng chờ Cán bộ duyệt.')
            else:
                # Tạo phiếu đăng ký mới (Trạng thái mặc định là CHO_DUYET trong Model)
                DangKyLop.objects.create(
                    sinh_vien=sinh_vien,
                    lop_hoc=lop_hoc,
                    file_minh_chung=file_minh_chung
                )
                messages.success(request, f'Đã gửi yêu cầu đăng ký lớp {lop_hoc.ten_lop} thành công!')

        except LopBoiDuong.DoesNotExist:
            messages.error(request, 'Lớp học không tồn tại hoặc đã đóng cổng đăng ký.')
        
        return redirect('danh_sach_lop')

    # 3. HIỂN THỊ DANH SÁCH LỚP (GET)
    # Lấy các lớp đang mở
    lops = LopBoiDuong.objects.filter(trang_thai=True).order_by('-id')
    
    # Lấy danh sách ID các lớp mà sinh viên này ĐÃ đăng ký (để ẩn nút đăng ký trên giao diện)
    da_dang_ky_ids = DangKyLop.objects.filter(sinh_vien=sinh_vien).values_list('lop_hoc_id', flat=True)

    return render(request, 'students/danh_sach_lop.html', {
        'lops': lops,
        'da_dang_ky_ids': da_dang_ky_ids,
        'sinh_vien': sinh_vien
    })
# ==========================================
# 4. TIỆN ÍCH DÀNH CHO CÁN BỘ
# ==========================================
def import_sinh_vien(request):
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

@login_required(login_url='dang_nhap')
def dashboard(request):
    try:
        # Tìm sinh viên khớp với tài khoản đang đăng nhập
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
        
        # Lấy lịch sử đăng ký lớp
        ds_dang_ky = DangKyLop.objects.filter(sinh_vien=sinh_vien).order_by('-thoi_gian_dk')
        
        # Lấy kết quả thi mới nhất
        ket_qua_thi = sinh_vien.lich_su_thi.all().order_by('-ngay_cap_nhat')[:5]

        return render(request, 'students/dashboard.html', {
            'sinh_vien': sinh_vien,
            'ds_dang_ky': ds_dang_ky,
            'ket_qua_thi': ket_qua_thi,
        })
    except SinhVien.DoesNotExist:
        messages.error(request, "Vui lòng cập nhật hồ sơ sinh viên.")
        return redirect('home')
    
@login_required(login_url='dang_nhap')
def cap_nhat_ho_so(request):
    if request.method == 'POST':
        try:
            sinh_vien = SinhVien.objects.get(mssv=request.user.username)
            
            # Lấy dữ liệu từ form gửi lên
            so_dien_thoai = request.POST.get('so_dien_thoai')
            email_ca_nhan = request.POST.get('email_ca_nhan')
            anh_dai_dien = request.FILES.get('anh_dai_dien')

            # Cập nhật thông tin
            if so_dien_thoai is not None:
                sinh_vien.so_dien_thoai = so_dien_thoai
            if email_ca_nhan is not None:
                sinh_vien.email_ca_nhan = email_ca_nhan
            if anh_dai_dien:
                sinh_vien.anh_dai_dien = anh_dai_dien

            sinh_vien.save()
            messages.success(request, 'Cập nhật hồ sơ cá nhân thành công!')
        except SinhVien.DoesNotExist:
            messages.error(request, 'Lỗi cập nhật. Không tìm thấy hồ sơ.')
            
    return redirect('dashboard')