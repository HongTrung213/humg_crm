from django.db import models
from django.db.models import Max
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
import pandas as pd

# --- 1. QUẢN LÝ HỒ SƠ & CHUẨN ĐẦU RA ---

class SinhVien(models.Model):
    mssv = models.CharField('Mã Sinh Viên', max_length=15, unique=True)
    ho_ten = models.CharField('Họ và Tên', max_length=100)
    khoa = models.CharField('Khoa', max_length=100, null=True, blank=True)
    lop = models.CharField('Lớp', max_length=50, null=True, blank=True)
    email_truong = models.EmailField('Email trường', unique=True, null=True, blank=True)

    class Meta:
        verbose_name = 'Sinh Viên'
        verbose_name_plural = 'Danh Sách Sinh Viên'

    def __str__(self):
        return f"{self.mssv} - {self.ho_ten}"

    # TỰ ĐỘNG TẠO TÀI KHOẢN VÀ EMAIL
    def save(self, *args, **kwargs):
        if not self.email_truong:
            self.email_truong = f"{self.mssv}@student.humg.edu.vn"
        super().save(*args, **kwargs)
        
        # Tự động tạo tài khoản với username là MSSV và mật khẩu mặc định
        if not User.objects.filter(username=self.mssv).exists():
            user = User.objects.create_user(username=self.mssv, password='cfihumg')
            user.first_name = self.ho_ten # Đồng bộ tên
            user.save()

    # ======================================================================
    # LOGIC LẤY ĐIỂM CAO NHẤT ĐỂ HIỂN THỊ (ĐÃ KHÔI PHỤC)
    # ======================================================================
    def _get_max_score(self, loai_mon):
        five_years_ago = timezone.now() - relativedelta(months=60)
        max_val = self.lich_su_thi.filter(
            mon_thi=loai_mon, 
            ngay_cap_nhat__gte=five_years_ago
        ).aggregate(Max('diem_thi'))['diem_thi__max']
        return max_val if max_val is not None else 0

    @property
    def max_diem_dau_vao(self): return self._get_max_score('TA_DAU_VAO')
    
    @property
    def max_diem_ngoai_ngu(self): return self._get_max_score('CDR_NGOAI_NGU')
    
    @property
    def max_diem_tin_hoc(self): return self._get_max_score('CDR_TIN_HOC')

    # ======================================================================
    # LOGIC KIỂM TRA CHỨNG CHỈ 
    # ======================================================================
    def _has_valid_cert(self, loai_cc):
        five_years_ago = timezone.now().date() - relativedelta(months=60)
        return self.ds_chung_chi.filter(
            loai=loai_cc, 
            trang_thai='DAT', 
            ngay_cap__gte=five_years_ago
        ).exists()

    @property
    def has_valid_cert_ngoai_ngu(self):
        return self._has_valid_cert('NGOAI_NGU')

    @property
    def has_valid_cert_tin_hoc(self):
        return self._has_valid_cert('TIN_HOC')

    # ======================================================================
    # LOGIC KIỂM TRA ĐẠT/CHƯA ĐẠT (TỔNG HỢP CẢ CHỨNG CHỈ VÀ LỊCH SỬ THI)
    # ======================================================================
    def _has_passed_exam(self, loai_mon):
        five_years_ago = timezone.now() - relativedelta(months=60)
        return self.lich_su_thi.filter(
            mon_thi=loai_mon,
            ngay_cap_nhat__gte=five_years_ago,
            ket_qua_dat=True
        ).exists()

    @property
    def check_dat_dau_vao(self):
        return self._has_passed_exam('TA_DAU_VAO')

    @property
    def check_dat_ngoai_ngu(self):
        return self.has_valid_cert_ngoai_ngu or self._has_passed_exam('CDR_NGOAI_NGU')

    @property
    def check_dat_tin_hoc(self):
        return self.has_valid_cert_tin_hoc or self._has_passed_exam('CDR_TIN_HOC')


class ChungChi(models.Model):
    LOAI_CC = [('NGOAI_NGU', 'Ngoại ngữ'), ('TIN_HOC', 'Tin học')]
    TRANG_THAI = [('CHO', 'Chờ xác minh'), ('DAT', 'Đã xác minh (Đạt)'), ('KHONG_DAT', 'Không hợp lệ')]

    sinh_vien = models.ForeignKey(SinhVien, on_delete=models.CASCADE, related_name='ds_chung_chi')
    loai = models.CharField('Loại chứng chỉ', max_length=20, choices=LOAI_CC)
    ten_chung_chi = models.CharField('Tên chứng chỉ', max_length=200)
    so_hieu = models.CharField('Số hiệu/Mã vạch', max_length=50)
    ngay_cap = models.DateField('Ngày cấp')
    file_minh_chung = models.FileField('Ảnh/PDF chứng chỉ', upload_to='certificates/%Y/')
    trang_thai = models.CharField('Trạng thái', max_length=20, choices=TRANG_THAI, default='CHO')
    ghi_chu_xac_minh = models.TextField('Ghi chú', blank=True)

    class Meta:
        verbose_name = 'Chứng chỉ sinh viên'
        verbose_name_plural = 'Quản lý Chứng chỉ'


# --- 2. QUẢN LÝ THI CỬ TẠI TRƯỜNG ---

class DotThi(models.Model):
    ma_dot = models.CharField('Mã đợt', max_length=20, unique=True)
    ten_dot = models.CharField('Tên đợt thi', max_length=200)
    thoi_gian_bat_dau = models.DateTimeField('Thời gian bắt đầu', default=timezone.now)
    thoi_gian_ket_thuc = models.DateTimeField('Thời gian kết thúc', default=timezone.now)
    file_thong_bao = models.FileField('File thông báo (PDF)', upload_to='announcements/', blank=True, null=True)
    trang_thai = models.BooleanField('Đang mở đăng ký', default=True)
    
    diem_chuan_ngoai_ngu = models.FloatField('Điểm chuẩn đạt Ngoại ngữ (Tổng)', default=5.0)
    diem_liet_ngoai_ngu = models.FloatField('Điểm liệt Ngoại ngữ (Mỗi phần)', default=0.0, help_text='Dưới mức này sẽ bị đánh rớt')
    
    diem_chuan_tin_hoc = models.FloatField('Điểm chuẩn đạt Tin học (Tổng)', default=5.0)
    diem_liet_tin_hoc = models.FloatField('Điểm liệt Tin học (Mỗi phần)', default=0.0)

    class Meta:
        verbose_name = 'Đợt thi'
        verbose_name_plural = 'Danh mục Đợt thi'

    def __str__(self):
        return self.ten_dot


class LichSuThi(models.Model):
    MON_THI = [('TA_DAU_VAO', 'Tiếng Anh đầu vào'), ('CDR_NGOAI_NGU', 'CĐR Ngoại ngữ'), ('CDR_TIN_HOC', 'CĐR Tin học')]
    sinh_vien = models.ForeignKey(SinhVien, on_delete=models.CASCADE, related_name='lich_su_thi')
    mon_thi = models.CharField('Môn thi', max_length=20, choices=MON_THI)
    dot_thi = models.ForeignKey(DotThi, on_delete=models.CASCADE, related_name='ket_qua')
    
    # ĐÃ KHÔI PHỤC: Bổ sung null=True, blank=True để ô Tổng điểm có thể tự động tính toán
    diem_thi = models.FloatField('Điểm tổng', null=True, blank=True, help_text='Bỏ trống để máy tự tính nếu có Điểm TP')
    diem_thanh_phan_1 = models.FloatField('Điểm thành phần 1 (Lý thuyết/Máy tính)', null=True, blank=True)
    diem_thanh_phan_2 = models.FloatField('Điểm thành phần 2 (Thực hành/Phỏng vấn)', null=True, blank=True)
    
    ket_qua_dat = models.BooleanField('Đạt chuẩn', default=False)
    ngay_cap_nhat = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Kết quả thi'
        verbose_name_plural = 'Kết quả các kỳ thi'

    def save(self, *args, **kwargs):
        # ĐÃ KHÔI PHỤC BƯỚC 1: Logic tự động tính điểm trung bình
        if self.diem_thanh_phan_1 is not None and self.diem_thanh_phan_2 is not None:
            self.diem_thi = round((self.diem_thanh_phan_1 + self.diem_thanh_phan_2) / 2, 2)
        
        if self.diem_thi is None:
            self.diem_thi = 0.0

        # BƯỚC 2: Logic kiểm tra điểm liệt và đạt chuẩn
        is_pass = False
        
        if self.mon_thi in ['TA_DAU_VAO', 'CDR_NGOAI_NGU']:
            if (self.diem_thanh_phan_1 is not None and self.diem_thanh_phan_1 <= self.dot_thi.diem_liet_ngoai_ngu) or \
               (self.diem_thanh_phan_2 is not None and self.diem_thanh_phan_2 <= self.dot_thi.diem_liet_ngoai_ngu):
                is_pass = False
            else:
                is_pass = self.diem_thi >= self.dot_thi.diem_chuan_ngoai_ngu
                
        elif self.mon_thi == 'CDR_TIN_HOC':
            if (self.diem_thanh_phan_1 is not None and self.diem_thanh_phan_1 <= self.dot_thi.diem_liet_tin_hoc) or \
               (self.diem_thanh_phan_2 is not None and self.diem_thanh_phan_2 <= self.dot_thi.diem_liet_tin_hoc):
                is_pass = False
            else:
                is_pass = self.diem_thi >= self.dot_thi.diem_chuan_tin_hoc

        self.ket_qua_dat = is_pass
        super().save(*args, **kwargs)


# --- 3. QUẢN LÝ LỚP BỒI DƯỠNG & ĐĂNG KÝ HỌC ---

class LopBoiDuong(models.Model):
    LOAI_LOP = [
        ('TA_TC', 'Tiếng Anh tăng cường'),
        ('TA_CDR', 'Ôn thi CĐR Ngoại ngữ'),
        ('TH_CDR', 'Ôn thi CĐR Tin học')
    ]

    ma_lop = models.CharField('Mã lớp', max_length=20, unique=True)
    ten_lop = models.CharField('Tên lớp', max_length=200)
    loai = models.CharField('Loại lớp', max_length=50, choices=LOAI_LOP)
    can_bo = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Cán bộ phụ trách')
    si_so_toi_da = models.IntegerField('Sĩ số tối đa', default=40)
    trang_thai = models.BooleanField('Đang mở đăng ký', default=True)
    
    sinh_vien = models.ManyToManyField(SinhVien, related_name='lop_hoc', blank=True)

    file_import_excel = models.FileField(
        'Upload File Excel nạp SV', 
        upload_to='temp_imports/', 
        blank=True, null=True, 
        help_text='Tải file Excel có cột "MSSV". Hệ thống tự động nạp sinh viên vào lớp khi lưu.'
    )

    class Meta:
        verbose_name = 'Lớp bồi dưỡng'
        verbose_name_plural = '1. Quản lý Lớp bồi dưỡng'

    def __str__(self):
        return f"{self.ten_lop} ({self.sinh_vien.count()}/{self.si_so_toi_da})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.file_import_excel:
            try:
                df = pd.read_excel(self.file_import_excel)
                if 'MSSV' in df.columns:
                    mssv_list = df['MSSV'].astype(str).str.strip().tolist()
                    sinh_viens_hop_le = SinhVien.objects.filter(mssv__in=mssv_list)
                    self.sinh_vien.add(*sinh_viens_hop_le)
            except Exception as e:
                print(f"Lỗi khi đọc file Excel: {e}")

            self.file_import_excel.delete(save=False)
            super().save(update_fields=['file_import_excel'])


class DangKyLop(models.Model):
    TRANG_THAI_DK = [
        ('CHO_DUYET', 'Chờ duyệt'),
        ('THANH_CONG', 'Đăng ký thành công'),
        ('DA_HUY', 'Đã hủy'),
    ]

    sinh_vien = models.ForeignKey(SinhVien, on_delete=models.CASCADE, related_name='ds_dang_ky_lop', verbose_name='Sinh viên')
    lop_hoc = models.ForeignKey(LopBoiDuong, on_delete=models.CASCADE, related_name='ds_dang_ky', verbose_name='Lớp học')
    
    file_minh_chung = models.FileField('Ảnh minh chứng (Biên lai)', upload_to='minh_chung_dk/%Y/%m/', blank=True, null=True)
    
    thoi_gian_dk = models.DateTimeField('Thời gian đăng ký', auto_now_add=True)
    trang_thai = models.CharField('Trạng thái', max_length=20, choices=TRANG_THAI_DK, default='CHO_DUYET')

    class Meta:
        verbose_name = 'Phiếu đăng ký học'
        verbose_name_plural = '2. Quản lý Đăng ký học'
        unique_together = ('sinh_vien', 'lop_hoc') 

    def __str__(self):
        return f"{self.sinh_vien.mssv} đăng ký {self.lop_hoc.ma_lop}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.trang_thai == 'THANH_CONG':
            self.lop_hoc.sinh_vien.add(self.sinh_vien)
        elif self.trang_thai in ['CHO_DUYET', 'DA_HUY']:
            self.lop_hoc.sinh_vien.remove(self.sinh_vien)