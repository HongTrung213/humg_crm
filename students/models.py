from django.db import models
from django.db.models import Max, Count
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.db.models.signals import post_delete
from django.dispatch import receiver
import pandas as pd
import os

# ==============================================================================
# DANH MỤC HỆ THỐNG (MASTER DATA)
# ==============================================================================
class Khoa(models.Model):
    ten_khoa = models.CharField('Tên Khoa/Viện', max_length=200, unique=True)
    
    class Meta:
        verbose_name = 'Danh mục Khoa'
        verbose_name_plural = '1. Danh mục Khoa/Viện'

    def __str__(self):
        return self.ten_khoa

# ==============================================================================
# DANH MỤC LOẠI CHỨNG CHỈ
# ==============================================================================
class DanhMucChungChi(models.Model):
    LOAI_CC = [
        ('NGOAI_NGU', 'Chuẩn đầu ra Ngoại ngữ'), 
        ('TIN_HOC', 'Chuẩn đầu ra Tin học')
    ]
    loai = models.CharField('Phân loại', max_length=20, choices=LOAI_CC)
    ten_chung_chi = models.CharField('Tên chứng chỉ', max_length=150, unique=True, help_text='VD: IELTS, TOEIC, MOS Word...')

    class Meta:
        verbose_name = 'Danh mục Chứng chỉ'
        verbose_name_plural = 'Danh mục Chứng chỉ'

    def __str__(self):
        return f"[{self.get_loai_display()}] {self.ten_chung_chi}"


# ==============================================================================
# PHÂN HỆ 1: QUẢN LÝ HỒ SƠ SINH VIÊN & CHỨNG CHỈ (CHUẨN ĐẦU RA)
# ==============================================================================
class SinhVien(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='ho_so')
    
    mssv = models.CharField('Mã Sinh Viên', max_length=15, unique=True)
    ho_ten = models.CharField('Họ và Tên', max_length=100)
    
    # KHÓA NGOẠI: Liên kết với Danh mục Khoa
    khoa = models.ForeignKey(Khoa, on_delete=models.SET_NULL, null=True, blank=True, related_name='sinh_vien_list', verbose_name='Khoa/Viện')
    lop = models.CharField('Lớp sinh hoạt', max_length=50, null=True, blank=True)
    
    # Thông tin liên lạc
    so_dien_thoai = models.CharField('Số điện thoại', max_length=15, null=True, blank=True)
    email_truong = models.EmailField('Email trường', unique=True, null=True, blank=True)
    email_ca_nhan = models.EmailField('Email cá nhân', null=True, blank=True)
    anh_dai_dien = models.ImageField('Ảnh đại diện', upload_to='profile_pics/', null=True, blank=True)

    class Meta:
        verbose_name = 'Sinh Viên'
        verbose_name_plural = '3. Quản lý Hồ sơ Sinh Viên'

    def __str__(self):
        return f"{self.mssv} - {self.ho_ten}"

    def save(self, *args, **kwargs):
        if not self.email_truong:
            self.email_truong = f"{self.mssv}@student.humg.edu.vn"
        super().save(*args, **kwargs)
        
        if not User.objects.filter(username=self.mssv).exists():
            user = User.objects.create_user(username=self.mssv, password='cfihumg')
            user.first_name = self.ho_ten
            user.save()

    # --- LOGIC LẤY ĐIỂM THI CAO NHẤT ---
    def _get_max_score(self, loai_mon):
        five_years_ago = timezone.now() - relativedelta(months=60)
        max_val = self.lich_su_thi.filter(
            mon_thi=loai_mon, 
            ngay_cap_nhat__gte=five_years_ago
        ).aggregate(Max('diem_tong'))['diem_tong__max'] # Sửa diem_thi thành diem_tong
        return max_val if max_val is not None else 0

    @property
    def max_diem_dau_vao(self): return self._get_max_score('TA_DAU_VAO')
    @property
    def max_diem_ngoai_ngu(self): return self._get_max_score('CDR_NGOAI_NGU')
    @property
    def max_diem_tin_hoc(self): return self._get_max_score('CDR_TIN_HOC')

    # --- LOGIC KIỂM TRA CHỨNG CHỈ HỢP LỆ THEO DANH MỤC ---
    def _has_valid_cert(self, loai_cc):
        five_years_ago = timezone.now().date() - relativedelta(months=60)
        
        # SỬA LỖI 1: Dùng đúng related_name là 'cac_chung_chi'
        qs = self.cac_chung_chi.filter(
            danh_muc__loai=loai_cc, 
            trang_thai='DAT', 
            ngay_cap__gte=five_years_ago
        )
        
        # SỬA LỖI 2: Đưa logic tích lũy 3/5 môn MOS vào
        if loai_cc == 'TIN_HOC':
            # 1. Nếu có bằng Tin học khác (VD: IC3, CNTT Cơ bản) -> ĐẠT luôn
            if qs.exclude(danh_muc__ten_chung_chi__icontains='MOS').exists():
                return True
            # 2. Nếu chỉ có MOS -> Phải đếm đủ 3 môn khác nhau mới ĐẠT
            so_luong_mos = qs.filter(danh_muc__ten_chung_chi__icontains='MOS').values('danh_muc').distinct().count()
            return so_luong_mos >= 3
            
        # Với Ngoại ngữ, chỉ cần có 1 chứng chỉ hợp lệ là Đạt
        return qs.exists()

    @property
    def has_valid_cert_ngoai_ngu(self): return self._has_valid_cert('NGOAI_NGU')
    @property
    def has_valid_cert_tin_hoc(self): return self._has_valid_cert('TIN_HOC')

    # --- LOGIC TỔNG HỢP KẾT QUẢ ĐẠT ---
    def _has_passed_exam(self, loai_mon):
        five_years_ago = timezone.now() - relativedelta(months=60)
        return self.lich_su_thi.filter(
            mon_thi=loai_mon, ngay_cap_nhat__gte=five_years_ago, ket_qua_dat=True
        ).exists()

    @property
    def check_dat_dau_vao(self): return self._has_passed_exam('TA_DAU_VAO')
    @property
    def check_dat_ngoai_ngu(self): return self.has_valid_cert_ngoai_ngu or self._has_passed_exam('CDR_NGOAI_NGU')
    @property
    def check_dat_tin_hoc(self): return self.has_valid_cert_tin_hoc or self._has_passed_exam('CDR_TIN_HOC')

    # THÊM ĐOẠN NÀY VÀO DƯỚI CÙNG CLASS SINH VIÊN:
    @property
    def ds_chung_chi(self):
        """Bí danh (Alias) giúp Frontend lấy danh sách chứng chỉ mà không cần sửa HTML"""
        return self.cac_chung_chi


# ==============================================================================
# 2. BẢNG TRANSACTION: HỒ SƠ CHỨNG CHỈ CỦA SINH VIÊN
# ==============================================================================
class ChungChi(models.Model):
    TRANG_THAI_DUYET = [
        ('CHO', 'Chờ xét duyệt'),
        ('DAT', 'Hợp lệ (Đạt)'),
        ('KHONG_DAT', 'Từ chối (Không đạt)')
    ]

    sinh_vien = models.ForeignKey('SinhVien', on_delete=models.CASCADE, related_name='cac_chung_chi')
    danh_muc = models.ForeignKey(DanhMucChungChi, on_delete=models.RESTRICT, verbose_name="Loại chứng chỉ")
    so_hieu = models.CharField('Số hiệu / ID', max_length=100, help_text="Dùng để chuyên viên tra cứu hậu kiểm")
    ngay_cap = models.DateField('Ngày cấp')
    
    diem_tong = models.FloatField('Điểm tổng', null=True, blank=True)
    diem_thanh_phan = models.CharField('Điểm thành phần (L/R/S/W)', max_length=100, null=True, blank=True)
    file_minh_chung = models.FileField('File minh chứng', upload_to='minh_chung_chung_chi/%Y/%m/')
    
    trang_thai = models.CharField('Trạng thái', max_length=20, choices=TRANG_THAI_DUYET, default='CHO')
    ghi_chu_xac_minh = models.TextField('Ghi chú của Chuyên viên', null=True, blank=True)
    
    ngay_nop = models.DateTimeField('Ngày nộp', auto_now_add=True)
    ngay_cap_nhat = models.DateTimeField('Lần cập nhật cuối', auto_now=True)

    class Meta:
        verbose_name = 'Hồ sơ Chứng chỉ'
        verbose_name_plural = 'Hồ sơ Chứng chỉ'
        unique_together = ['sinh_vien', 'so_hieu'] # Khóa chống nộp trùng lặp

    def __str__(self):
        return f"{self.sinh_vien.mssv} - {self.danh_muc.ten_chung_chi} ({self.get_trang_thai_display()})"

    @property
    def con_han_su_dung(self):
        """Kiểm tra chứng chỉ còn hạn 60 tháng (5 năm)"""
        if not self.ngay_cap: return False
        return timezone.now().date() <= (self.ngay_cap + relativedelta(months=60))

# ==============================================================================
# PHÂN HỆ 2: QUẢN LÝ THI CỬ NỘI BỘ
# ==============================================================================
class DotThi(models.Model):
    ma_dot = models.CharField('Mã đợt thi', max_length=20, unique=True)
    ten_dot = models.CharField('Tên đợt thi', max_length=200)
    thoi_gian_bat_dau = models.DateTimeField('Thời gian bắt đầu', default=timezone.now)
    thoi_gian_ket_thuc = models.DateTimeField('Thời gian kết thúc', default=timezone.now)
    file_thong_bao = models.FileField('File thông báo (PDF)', upload_to='announcements/', blank=True, null=True)
    #trang_thai = models.BooleanField('Đang mở đăng ký', default=True)
    
    # Cấu hình điểm
    diem_chuan_ngoai_ngu = models.FloatField('Điểm chuẩn Ngoại ngữ', default=5.0)
    diem_liet_ngoai_ngu = models.FloatField('Điểm liệt Ngoại ngữ', default=0.0)
    diem_chuan_tin_hoc = models.FloatField('Điểm chuẩn Tin học', default=5.0)
    diem_liet_tin_hoc = models.FloatField('Điểm liệt Tin học', default=0.0)

    class Meta:
        verbose_name = 'Đợt thi'
        verbose_name_plural = '5. Cấu hình Đợt thi'

    def __str__(self): return self.ten_dot
    
    def trang_thai_hien_tai(self):
        """
        Logic tính toán trạng thái Real-time:
        Trả về 1: Đang hoạt động | Trả về 2: Sắp diễn ra | Trả về 0: Đã kết thúc
        """
        now = timezone.now()
        if not self.thoi_gian_bat_dau or not self.thoi_gian_ket_thuc:
            return 0 # An toàn lỗi dữ liệu
            
        if now < self.thoi_gian_bat_dau:
            return 2 # Sắp tới
        elif self.thoi_gian_bat_dau <= now <= self.thoi_gian_ket_thuc:
            return 1 # Đang hoạt động
        else:
            return 0 # Đã đóng/Kết thúc


class LichSuThi(models.Model):
    # --- 1. ÉP BUỘC TỰ NHẢY SỐ ID (CHỐNG LỖI UNIQUE) ---
    id = models.BigAutoField(primary_key=True)

    MON_THI = [('TA_DAU_VAO', 'Tiếng Anh đầu vào'), ('CDR_NGOAI_NGU', 'CĐR Ngoại ngữ'), ('CDR_TIN_HOC', 'CĐR Tin học')]
    
    sinh_vien = models.ForeignKey(SinhVien, on_delete=models.CASCADE, related_name='lich_su_thi')
    mon_thi = models.CharField('Môn thi', max_length=20, choices=MON_THI)
    dot_thi = models.ForeignKey(DotThi, on_delete=models.CASCADE, related_name='ket_qua')
    
    # --- BỘ LỊCH THI ---
    sbd = models.CharField(max_length=50, null=True, blank=True, verbose_name="Số báo danh")
    ngay_thi = models.CharField(max_length=50, null=True, blank=True, verbose_name="Ngày thi 1")
    ca_thi = models.CharField(max_length=50, null=True, blank=True, verbose_name="Ca thi 1")
    phong_thi = models.CharField(max_length=50, null=True, blank=True, verbose_name="Phòng thi 1")
    
    ngay_thi_2 = models.CharField(max_length=50, null=True, blank=True, verbose_name="Ngày thi Nói")
    ca_thi_2 = models.CharField(max_length=50, null=True, blank=True, verbose_name="Ca thi Nói")
    phong_thi_2 = models.CharField(max_length=50, null=True, blank=True, verbose_name="Phòng thi Nói")
    
    # --- BỘ ĐIỂM THI ---
    diem_thanh_phan_1 = models.FloatField(null=True, blank=True, verbose_name="Nghe / Trắc nghiệm")
    diem_thanh_phan_2 = models.FloatField(null=True, blank=True, verbose_name="Đọc / Thực hành")
    diem_thanh_phan_3 = models.FloatField(null=True, blank=True, verbose_name="Viết")
    diem_thanh_phan_4 = models.FloatField(null=True, blank=True, verbose_name="Nói")
    diem_tong = models.FloatField(null=True, blank=True, verbose_name="Tổng điểm / Đánh giá")
    
    xep_loai = models.CharField(max_length=100, null=True, blank=True, verbose_name="Xếp loại")
    ghi_chu = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ghi chú")
    
    ket_qua_dat = models.BooleanField('Kết quả Đạt', default=False)
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Điểm thi / Lịch thi'
        verbose_name_plural = '6. Quản lý Điểm thi'

    def save(self, *args, **kwargs):
        # 1. Tính tổng điểm
        diems = [self.diem_thanh_phan_1, self.diem_thanh_phan_2, self.diem_thanh_phan_3, self.diem_thanh_phan_4]
        valid_diems = [d for d in diems if d is not None]

        if self.diem_tong is None and valid_diems:
            self.diem_tong = round(sum(valid_diems), 2)

        # 2. Logic xét Đạt/Trượt
        is_pass = False
        xl_str = str(self.xep_loai).lower() if self.xep_loai else ""
        gc_str = str(self.ghi_chu).lower() if self.ghi_chu else ""

        # Ưu tiên 1: Chặn đứng Vắng thi, Không đạt
        if any(k in xl_str or k in gc_str for k in ['vắng', 'bỏ thi', 'đình chỉ', 'không đạt']):
            is_pass = False
            
        # Ưu tiên 2: Xét chữ "Đủ điều kiện", "Đạt", "B1"...
        elif any(k in xl_str for k in ['đủ điều kiện', 'đạt', 'pass', 'b1', 'b2', 'a2', 'c1']):
            is_pass = True
            
        # Ưu tiên 3: Xét bằng Số học
        else:
            d_tong = self.diem_tong or 0
            if self.mon_thi in ['TA_DAU_VAO', 'CDR_NGOAI_NGU']:
                d_chuan = self.dot_thi.diem_chuan_ngoai_ngu
                d_liet = self.dot_thi.diem_liet_ngoai_ngu
            else:
                d_chuan = self.dot_thi.diem_chuan_tin_hoc
                d_liet = self.dot_thi.diem_liet_tin_hoc

            bi_liet = any(d <= d_liet for d in valid_diems) if d_liet >= 0 else False
            
            if not bi_liet and d_tong >= d_chuan:
                is_pass = True

        self.ket_qua_dat = is_pass
        
        # 3. CHỈ GỌI LỆNH SAVE ĐÚNG 1 LẦN DUY NHẤT Ở CUỐI CÙNG
        super().save(*args, **kwargs)

        
# ==============================================================================
# PHÂN HỆ 3: QUẢN LÝ LỚP HỌC
# ==============================================================================
class LopBoiDuong(models.Model):
    LOAI_LOP = [('TA_TC', 'Tiếng Anh tăng cường'), ('TA_CDR', 'Ôn thi CĐR Ngoại ngữ'), ('TH_CDR', 'Ôn thi CĐR Tin học')]
    ma_lop = models.CharField('Mã lớp', max_length=20, unique=True)
    ten_lop = models.CharField('Tên lớp', max_length=200)
    loai = models.CharField('Loại lớp', max_length=50, choices=LOAI_LOP)
    can_bo = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    si_so_toi_da = models.IntegerField('Sĩ số tối đa', default=40)
    trang_thai = models.BooleanField('Đang mở đăng ký', default=True)
    sinh_vien = models.ManyToManyField(SinhVien, related_name='lop_hoc', blank=True)
    file_import_excel = models.FileField('Excel nạp SV', upload_to='temp_imports/', blank=True, null=True)

    class Meta:
        verbose_name = 'Lớp bồi dưỡng'
        verbose_name_plural = '7. Quản lý Lớp bồi dưỡng'

    def __str__(self): return f"{self.ten_lop} ({self.sinh_vien.count()}/{self.si_so_toi_da})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.file_import_excel:
            try:
                df = pd.read_excel(self.file_import_excel)
                if 'MSSV' in df.columns:
                    mssv_list = df['MSSV'].astype(str).str.strip().tolist()
                    sinh_viens_hop_le = SinhVien.objects.filter(mssv__in=mssv_list)
                    self.sinh_vien.add(*sinh_viens_hop_le)
            except: pass
            self.file_import_excel.delete(save=False)
            super().save(update_fields=['file_import_excel'])


class DangKyLop(models.Model):
    TRANG_THAI_DK = [('CHO_DUYET', 'Chờ duyệt'), ('THANH_CONG', 'Đã duyệt'), ('DA_HUY', 'Đã hủy')]
    sinh_vien = models.ForeignKey(SinhVien, on_delete=models.CASCADE, related_name='ds_dang_ky_lop')
    lop_hoc = models.ForeignKey(LopBoiDuong, on_delete=models.CASCADE, related_name='ds_dang_ky')
    file_minh_chung = models.FileField('Biên lai', upload_to='minh_chung_dk/%Y/%m/', blank=True, null=True)
    thoi_gian_dk = models.DateTimeField('Thời gian đăng ký', auto_now_add=True)
    trang_thai = models.CharField('Trạng thái', max_length=20, choices=TRANG_THAI_DK, default='CHO_DUYET')

    class Meta:
        verbose_name = 'Phiếu đăng ký'
        verbose_name_plural = '8. Duyệt Đăng ký học'
        unique_together = ('sinh_vien', 'lop_hoc')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.trang_thai == 'THANH_CONG': self.lop_hoc.sinh_vien.add(self.sinh_vien)
        elif self.trang_thai in ['CHO_DUYET', 'DA_HUY']: self.lop_hoc.sinh_vien.remove(self.sinh_vien)

# ==============================================================================
# HÀM TỰ ĐỘNG DỌN DẸP FILE RÁC TRÊN SERVER KHI XÓA BẢN GHI
# ==============================================================================
@receiver(post_delete, sender=ChungChi)
@receiver(post_delete, sender=DangKyLop)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """Xóa file minh chứng khỏi ổ cứng khi bản ghi bị xóa"""
    field_name = 'file_minh_chung'
    if hasattr(instance, field_name):
        file = getattr(instance, field_name)
        if file and os.path.isfile(file.path):
            os.remove(file.path)