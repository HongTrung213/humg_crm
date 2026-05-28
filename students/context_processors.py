
from .models import SinhVien, ThongBao


def sinh_vien_global(request):
    """Đưa hồ sơ sinh viên và số thông báo/cảnh báo ra toàn bộ template."""
    sinh_vien = None
    so_thong_bao_cham_soc = 0

    if request.user.is_authenticated:
        sinh_vien = SinhVien.objects.filter(user=request.user).first()
        if not sinh_vien:
            sinh_vien = SinhVien.objects.filter(mssv=request.user.username).first()
        if not sinh_vien and request.user.email:
            sinh_vien = SinhVien.objects.filter(email_truong__iexact=request.user.email).first()

        if sinh_vien:
            so_thong_bao_cham_soc = sum(
                1 for tb in ThongBao.objects.filter(is_active=True) if tb.phu_hop_voi_sinh_vien(sinh_vien)
            )

    return {
        'sinh_vien_global': sinh_vien,
        'so_thong_bao_cham_soc': so_thong_bao_cham_soc,
    }
