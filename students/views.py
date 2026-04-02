import pandas as pd
from django.shortcuts import render
from django.contrib import messages
from .models import SinhVien
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import SinhVien, LopBoiDuong, DangKyLop
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import SinhVien, LopBoiDuong, DangKyLop


def import_sinh_vien(request):
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        
        try:
            # Đọc file bằng Pandas
            df = pd.read_excel(excel_file)
            count = 0
            
            # Quét từng dòng trong Excel. Giả sử cột trong Excel tên là: MSSV, HoTen, Khoa, Email
            for index, row in df.iterrows():
                # update_or_create: Có MSSV rồi thì cập nhật, chưa có thì tạo mới
                SinhVien.objects.update_or_create(
                    mssv=str(row['MSSV']).strip(),
                    defaults={
                        'ho_ten': str(row['HoTen']).strip(),
                        'khoa': str(row['Khoa']).strip(),
                        'email': str(row['Email']).strip() if pd.notna(row['Email']) else '',
                    }
                )
                count += 1
                
            messages.success(request, f'Thành công! Đã nhập/cập nhật {count} sinh viên vào hệ thống.')
        except Exception as e:
            messages.error(request, f'Lỗi đọc file: Vui lòng kiểm tra lại cấu trúc cột Excel. Chi tiết lỗi: {e}')
            
    return render(request, 'students/import_excel.html')

from django.shortcuts import render
from .models import SinhVien

def tra_cuu(request):
    query_mssv = request.GET.get('mssv', '').strip()
    sinh_vien = None
    thong_bao = None
    lich_su_thi = None  # Khởi tạo biến lưu lịch sử thi

    if query_mssv:
        try:
            sinh_vien = SinhVien.objects.get(mssv=query_mssv)
            # Kéo toàn bộ lịch sử thi của sinh viên này ra
            lich_su_thi = sinh_vien.lich_su_thi.all()
        except SinhVien.DoesNotExist:
            thong_bao = f"Không tìm thấy sinh viên nào với mã số: {query_mssv}"

    return render(request, 'students/tra_cuu.html', {
        'sinh_vien': sinh_vien,
        'query_mssv': query_mssv,
        'thong_bao': thong_bao,
        'lich_su_thi': lich_su_thi  # Nhớ truyền biến này ra ngoài template
    })


def danh_sach_lop(request):
    # Chỉ lấy các lớp đang mở đăng ký
    lops = LopBoiDuong.objects.filter(trang_thai=True)
    return render(request, 'students/danh_sach_lop.html', {'lops': lops})

def dang_ky_lop(request, class_id):
    lop_hoc = get_object_or_404(LopBoiDuong, id=class_id)
    
    if request.method == 'POST':
        mssv = request.POST.get('mssv', '').strip()
        try:
            sinh_vien = SinhVien.objects.get(mssv=mssv)
            
            # Kiểm tra xem sinh viên đã đăng ký lớp này chưa
            if DangKyLop.objects.filter(sinh_vien=sinh_vien, lop_hoc=lop_hoc).exists():
                messages.warning(request, f'MSSV {mssv} đã đăng ký lớp này từ trước, vui lòng chờ duyệt!')
            else:
                # Tạo phiếu đăng ký mới với trạng thái mặc định là CHO_DUYET
                DangKyLop.objects.create(sinh_vien=sinh_vien, lop_hoc=lop_hoc)
                messages.success(request, f'Chúc mừng {sinh_vien.ho_ten}! Bạn đã đăng ký thành công lớp {lop_hoc.ten_lop}.')
            
            return redirect('danh_sach_lop')
            
        except SinhVien.DoesNotExist:
            messages.error(request, f'Lỗi: Không tìm thấy sinh viên nào có MSSV {mssv} trên hệ thống.')
            
    return render(request, 'students/dang_ky_lop.html', {'lop_hoc': lop_hoc})

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

# --- LOGIC ĐĂNG NHẬP / ĐĂNG XUẤT ---
def dang_nhap(request):
    if request.method == 'POST':
        mssv = request.POST.get('mssv')
        mat_khau = request.POST.get('password')
        user = authenticate(request, username=mssv, password=mat_khau)
        if user is not None:
            login(request, user)
            return redirect('danh_sach_lop') # Đăng nhập thành công thì đẩy vào xem lớp
        else:
            messages.error(request, 'Mã sinh viên hoặc mật khẩu không chính xác!')
    return render(request, 'students/login.html')

def dang_xuat(request):
    logout(request)
    return redirect('dang_nhap')

# --- LOGIC ĐĂNG KÝ LỚP MỚI (YÊU CẦU ĐĂNG NHẬP) ---
@login_required(login_url='dang_nhap')
def dang_ky_lop(request, class_id):
    lop_hoc = get_object_or_404(LopBoiDuong, id=class_id)
    # Lấy thông tin sinh viên từ tài khoản đang đăng nhập
    try:
        sinh_vien = SinhVien.objects.get(mssv=request.user.username)
    except SinhVien.DoesNotExist:
        messages.error(request, 'Tài khoản chưa được liên kết hồ sơ, vui lòng liên hệ Admin.')
        return redirect('danh_sach_lop')

    if request.method == 'POST':
        # Lấy file ảnh được tải lên từ Form
        file_anh = request.FILES.get('file_minh_chung')
        
        if DangKyLop.objects.filter(sinh_vien=sinh_vien, lop_hoc=lop_hoc).exists():
            messages.warning(request, 'Bạn đã gửi yêu cầu đăng ký lớp này từ trước!')
        else:
            DangKyLop.objects.create(
                sinh_vien=sinh_vien, 
                lop_hoc=lop_hoc,
                file_minh_chung=file_anh # Lưu file vào DB
            )
            messages.success(request, f'Đã nộp đơn đăng ký lớp {lop_hoc.ten_lop} thành công. Vui lòng chờ duyệt.')
        return redirect('danh_sach_lop')
        
    return render(request, 'students/dang_ky_lop.html', {'lop_hoc': lop_hoc, 'sinh_vien': sinh_vien})

# --- LOGIC ĐĂNG NHẬP / ĐĂNG XUẤT ---
def dang_nhap(request):
    if request.method == 'POST':
        mssv = request.POST.get('mssv')
        mat_khau = request.POST.get('password')
        user = authenticate(request, username=mssv, password=mat_khau)
        if user is not None:
            login(request, user)
            return redirect('danh_sach_lop') # Đăng nhập thành công thì đẩy vào xem lớp
        else:
            messages.error(request, 'Mã sinh viên hoặc mật khẩu không chính xác!')
    return render(request, 'students/login.html')

def dang_xuat(request):
    logout(request)
    return redirect('dang_nhap')