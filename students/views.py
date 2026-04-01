import pandas as pd
from django.shortcuts import render
from django.contrib import messages
from .models import SinhVien

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
    # Lấy MSSV từ thanh tìm kiếm (nếu có)
    query_mssv = request.GET.get('mssv', '').strip()
    sinh_vien = None
    thong_bao = None

    if query_mssv:
        try:
            # Truy vấn Database tìm sinh viên khớp mã
            sinh_vien = SinhVien.objects.get(mssv=query_mssv)
        except SinhVien.DoesNotExist:
            thong_bao = f"Không tìm thấy sinh viên nào với mã số: {query_mssv}"

    return render(request, 'students/tra_cuu.html', {
        'sinh_vien': sinh_vien,
        'query_mssv': query_mssv,
        'thong_bao': thong_bao
    })