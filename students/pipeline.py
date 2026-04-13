# File: students/pipeline.py
from .models import SinhVien

def link_to_existing_student(backend, user, response, *args, **kwargs):
    """
    Pipeline: Nối tài khoản SSO với dữ liệu SinhVien đã nhập sẵn qua Email.
    """
    # Lấy email từ Google/Microsoft trả về
    email = response.get('email')
    if not email:
        return

    # Lấy tên từ tài khoản (phòng trường hợp tạo mới)
    ho_ten_sso = response.get('name', 'Sinh viên HUMG')
    # Tách lấy MSSV từ email (VD: 2121050003@student.humg.edu.vn -> 2121050003)
    mssv_tu_email = email.split('@')[0]

    try:
        # 1. Tìm xem Admin đã import ông sinh viên này vào hệ thống chưa?
        sinh_vien = SinhVien.objects.get(email_truong=email)
        
        # 2. Nếu tìm thấy, nhưng chưa liên kết với User đăng nhập thì tiến hành liên kết
        if not sinh_vien.user:
            sinh_vien.user = user
            sinh_vien.save()
            
    except SinhVien.DoesNotExist:
        # 3. Nếu Admin chưa import file Excel, hệ thống TỰ ĐỘNG tạo mới hồ sơ sinh viên
        SinhVien.objects.create(
            user=user,
            mssv=mssv_tu_email,
            ho_ten=ho_ten_sso,
            email_truong=email
        )