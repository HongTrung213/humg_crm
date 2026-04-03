from .models import SinhVien

def sinh_vien_global(request):
    # Trả về thông tin sinh viên cho tất cả các trang HTML nếu đã đăng nhập
    if request.user.is_authenticated:
        try:
            sv = SinhVien.objects.get(mssv=request.user.username)
            return {'sinh_vien_global': sv}
        except SinhVien.DoesNotExist:
            pass
    return {'sinh_vien_global': None}