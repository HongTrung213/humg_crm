import os

import pandas as pd
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Max
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone


# ==============================================================================
# DANH MỤC HỆ THỐNG (MASTER DATA)
# ==============================================================================
class Khoa(models.Model):
    ma_khoa = models.CharField(
        'Mã Khoa',
        max_length=10,
        unique=True,
        null=True,
        blank=True,
        help_text='VD: 105, 101, 102... dùng để tự động phân khoa từ MSSV',
    )
    ten_khoa = models.CharField('Tên Khoa/Viện', max_length=200, unique=True)

    class Meta:
        verbose_name = 'Danh mục Khoa'
        verbose_name_plural = '1. Danh mục Khoa/Viện'
        ordering = ['ma_khoa', 'ten_khoa']

    def __str__(self):
        if self.ma_khoa:
            return f"[{self.ma_khoa}] {self.ten_khoa}"
        return self.ten_khoa


class DanhMucChungChi(models.Model):
    LOAI_CC = [
        ('NGOAI_NGU', 'Chuẩn đầu ra Ngoại ngữ'),
        ('TIN_HOC', 'Chuẩn đầu ra Tin học'),
    ]

    loai = models.CharField('Phân loại', max_length=20, choices=LOAI_CC)
    ten_chung_chi = models.CharField(
        'Tên chứng chỉ',
        max_length=150,
        unique=True,
        help_text='VD: IELTS, TOEIC, MOS Word...',
    )

    class Meta:
        verbose_name = 'Danh mục Chứng chỉ'
        verbose_name_plural = '2. Danh mục Chứng chỉ'
        ordering = ['loai', 'ten_chung_chi']

    def __str__(self):
        return f"[{self.get_loai_display()}] {self.ten_chung_chi}"


# ==============================================================================
# PHÂN HỆ 1: QUẢN LÝ HỒ SƠ SINH VIÊN & CHỨNG CHỈ
# ==============================================================================
class SinhVien(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ho_so',
    )
    mssv = models.CharField('Mã Sinh Viên', max_length=15, unique=True)
    ho_ten = models.CharField('Họ và Tên', max_length=100)
    khoa = models.ForeignKey(
        Khoa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sinh_vien_list',
        verbose_name='Khoa/Viện',
    )
    lop = models.CharField('Lớp sinh hoạt', max_length=50, null=True, blank=True)
    so_dien_thoai = models.CharField('Số điện thoại', max_length=15, null=True, blank=True)
    email_truong = models.EmailField('Email trường', unique=True, null=True, blank=True)
    email_ca_nhan = models.EmailField('Email cá nhân', null=True, blank=True)
    anh_dai_dien = models.ImageField('Ảnh đại diện', upload_to='profile_pics/', null=True, blank=True)

    class Meta:
        verbose_name = 'Sinh Viên'
        verbose_name_plural = '3. Quản lý Hồ sơ Sinh Viên'
        ordering = ['-mssv']

    def __str__(self):
        return f"{self.mssv} - {self.ho_ten}"

    def save(self, *args, **kwargs):
        """
        Tự đồng bộ tài khoản User theo MSSV.
        Mật khẩu mặc định cho sinh viên tạo tự động: cfihumg.
        """
        if not self.email_truong and self.mssv:
            self.email_truong = f"{self.mssv}@student.humg.edu.vn"

        if not self.user_id and self.mssv:
            user, created = User.objects.get_or_create(
                username=self.mssv,
                defaults={
                    'first_name': self.ho_ten,
                    'email': self.email_truong or '',
                    'is_active': True,
                },
            )
            if created:
                user.set_password('cfihumg')
            else:
                user.first_name = self.ho_ten
                if self.email_truong:
                    user.email = self.email_truong
            user.save()
            self.user = user

        super().save(*args, **kwargs)

    # --- LOGIC LẤY ĐIỂM THI CAO NHẤT TRONG 60 THÁNG ---
    def _get_max_score(self, loai_mon):
        five_years_ago = timezone.now() - relativedelta(months=60)
        max_val = self.lich_su_thi.filter(
            mon_thi=loai_mon,
            ngay_cap_nhat__gte=five_years_ago,
        ).aggregate(Max('diem_tong'))['diem_tong__max']
        return max_val if max_val is not None else 0

    @property
    def max_diem_dau_vao(self):
        return self._get_max_score('TA_DAU_VAO')

    @property
    def max_diem_ngoai_ngu(self):
        return self._get_max_score('CDR_NGOAI_NGU')

    @property
    def max_diem_tin_hoc(self):
        return self._get_max_score('CDR_TIN_HOC')

    # --- LOGIC KIỂM TRA CHỨNG CHỈ HỢP LỆ ---
    def _has_valid_cert(self, loai_cc):
        five_years_ago = timezone.now().date() - relativedelta(months=60)
        qs = self.cac_chung_chi.filter(
            danh_muc__loai=loai_cc,
            trang_thai='DAT',
            ngay_cap__gte=five_years_ago,
        )

        if loai_cc == 'TIN_HOC':
            # Nếu có chứng chỉ Tin học khác MOS thì đạt luôn.
            if qs.exclude(danh_muc__ten_chung_chi__icontains='MOS').exists():
                return True
            # Nếu dùng MOS thì cần đủ 3 module khác nhau.
            so_luong_mos = qs.filter(
                danh_muc__ten_chung_chi__icontains='MOS'
            ).values('danh_muc').distinct().count()
            return so_luong_mos >= 3

        return qs.exists()

    @property
    def has_valid_cert_ngoai_ngu(self):
        return self._has_valid_cert('NGOAI_NGU')

    @property
    def has_valid_cert_tin_hoc(self):
        return self._has_valid_cert('TIN_HOC')

    def _has_passed_exam(self, loai_mon):
        five_years_ago = timezone.now() - relativedelta(months=60)
        return self.lich_su_thi.filter(
            mon_thi=loai_mon,
            ngay_cap_nhat__gte=five_years_ago,
            ket_qua_dat=True,
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

    @property
    def ds_chung_chi(self):
        return self.cac_chung_chi

    @property
    def nam_nhap_hoc(self):
        try:
            return 2000 + int(str(self.mssv)[:2])
        except (ValueError, TypeError):
            return None

    @property
    def tien_do_nam_tu(self):
        if not self.nam_nhap_hoc:
            return False
        now = timezone.now()
        so_nam_da_hoc = now.year - self.nam_nhap_hoc
        if so_nam_da_hoc >= 4:
            return True
        if so_nam_da_hoc == 3 and now.month >= 8:
            return True
        return False

    @property
    def dat_chuan_dau_ra(self):
        return self.check_dat_tin_hoc and self.check_dat_ngoai_ngu

    @property
    def chua_dat_chuan_dau_ra(self):
        return not self.dat_chuan_dau_ra


class ChungChi(models.Model):
    TRANG_THAI_DUYET = [
        ('CHO', 'Chờ xét duyệt'),
        ('DAT', 'Hợp lệ (Đạt)'),
        ('KHONG_DAT', 'Từ chối (Không đạt)'),
    ]

    sinh_vien = models.ForeignKey('SinhVien', on_delete=models.CASCADE, related_name='cac_chung_chi')
    danh_muc = models.ForeignKey(DanhMucChungChi, on_delete=models.RESTRICT, verbose_name='Loại chứng chỉ')
    so_hieu = models.CharField('Số hiệu / ID', max_length=100, help_text='Dùng để chuyên viên tra cứu hậu kiểm')
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
        verbose_name_plural = '4. Hồ sơ Chứng chỉ'
        unique_together = ['sinh_vien', 'so_hieu']
        ordering = ['-ngay_nop']

    def __str__(self):
        return f"{self.sinh_vien.mssv} - {self.danh_muc.ten_chung_chi} ({self.get_trang_thai_display()})"

    @property
    def con_han_su_dung(self):
        if not self.ngay_cap:
            return False
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
    diem_chuan_ngoai_ngu = models.FloatField('Điểm chuẩn Ngoại ngữ', default=5.0)
    diem_liet_ngoai_ngu = models.FloatField('Điểm liệt Ngoại ngữ', default=0.0)
    diem_chuan_tin_hoc = models.FloatField('Điểm chuẩn Tin học', default=5.0)
    diem_liet_tin_hoc = models.FloatField('Điểm liệt Tin học', default=0.0)

    class Meta:
        verbose_name = 'Đợt thi'
        verbose_name_plural = '5. Cấu hình Đợt thi'
        ordering = ['-thoi_gian_bat_dau']

    def __str__(self):
        return self.ten_dot

    def trang_thai_hien_tai(self):
        now = timezone.now()
        if not self.thoi_gian_bat_dau or not self.thoi_gian_ket_thuc:
            return 0
        if now < self.thoi_gian_bat_dau:
            return 2
        if self.thoi_gian_bat_dau <= now <= self.thoi_gian_ket_thuc:
            return 1
        return 0


class LichSuThi(models.Model):
    id = models.BigAutoField(primary_key=True)

    MON_THI = [
        ('TA_DAU_VAO', 'Tiếng Anh đầu vào'),
        ('CDR_NGOAI_NGU', 'CĐR Ngoại ngữ'),
        ('CDR_TIN_HOC', 'CĐR Tin học'),
    ]

    sinh_vien = models.ForeignKey(SinhVien, on_delete=models.CASCADE, related_name='lich_su_thi')
    mon_thi = models.CharField('Môn thi', max_length=20, choices=MON_THI)
    dot_thi = models.ForeignKey(DotThi, on_delete=models.CASCADE, related_name='ket_qua')

    sbd = models.CharField('Số báo danh', max_length=50, null=True, blank=True)
    ngay_thi = models.CharField('Ngày thi 1', max_length=50, null=True, blank=True)
    ca_thi = models.CharField('Ca thi 1', max_length=50, null=True, blank=True)
    phong_thi = models.CharField('Phòng thi 1', max_length=50, null=True, blank=True)
    ngay_thi_2 = models.CharField('Ngày thi Nói', max_length=50, null=True, blank=True)
    ca_thi_2 = models.CharField('Ca thi Nói', max_length=50, null=True, blank=True)
    phong_thi_2 = models.CharField('Phòng thi Nói', max_length=50, null=True, blank=True)

    diem_thanh_phan_1 = models.FloatField('Nghe / Trắc nghiệm', null=True, blank=True)
    diem_thanh_phan_2 = models.FloatField('Đọc / Thực hành', null=True, blank=True)
    diem_thanh_phan_3 = models.FloatField('Viết', null=True, blank=True)
    diem_thanh_phan_4 = models.FloatField('Nói', null=True, blank=True)
    diem_tong = models.FloatField('Tổng điểm / Đánh giá', null=True, blank=True)
    xep_loai = models.CharField('Xếp loại', max_length=100, null=True, blank=True)
    ghi_chu = models.CharField('Ghi chú', max_length=255, null=True, blank=True)
    ket_qua_dat = models.BooleanField('Kết quả Đạt', default=False)
    co_bao_luu = models.BooleanField('Đã ghép điểm bảo lưu', default=False)
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Điểm thi / Lịch thi'
        verbose_name_plural = '6. Quản lý Điểm thi'
        indexes = [
            models.Index(fields=['dot_thi', 'mon_thi']),
            models.Index(fields=['sbd']),
        ]

    def save(self, *args, **kwargs):
        diems = [
            self.diem_thanh_phan_1,
            self.diem_thanh_phan_2,
            self.diem_thanh_phan_3,
            self.diem_thanh_phan_4,
        ]
        valid_diems = [d for d in diems if d is not None]

        if self.diem_tong is None and valid_diems:
            self.diem_tong = round(sum(valid_diems), 2)

        is_pass = False
        xl_str = str(self.xep_loai).lower() if self.xep_loai else ''
        gc_str = str(self.ghi_chu).lower() if self.ghi_chu else ''

        if any(k in xl_str or k in gc_str for k in ['vắng', 'vang', 'bỏ thi', 'bo thi', 'đình chỉ', 'dinh chi', 'không đạt', 'khong dat']):
            is_pass = False
        elif any(k in xl_str for k in ['đủ điều kiện', 'du dieu kien', 'đạt', 'dat', 'pass', 'b1', 'b2', 'a2', 'c1']):
            is_pass = True
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
        super().save(*args, **kwargs)


# ==============================================================================
# PHÂN HỆ 3: QUẢN LÝ LỚP HỌC
# ==============================================================================
class LopBoiDuong(models.Model):
    LOAI_LOP = [
        ('TA_TC', 'Tiếng Anh tăng cường'),
        ('TA_CDR', 'Ôn thi CĐR Ngoại ngữ'),
        ('TH_CDR', 'Ôn thi CĐR Tin học'),
    ]

    ma_lop = models.CharField('Mã lớp', max_length=20, unique=True)
    ten_lop = models.CharField('Tên lớp', max_length=200)
    loai = models.CharField('Loại lớp', max_length=50, choices=LOAI_LOP)
    can_bo = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Cán bộ phụ trách')
    si_so_toi_da = models.IntegerField('Sĩ số tối đa', default=40)
    ngay_khai_giang = models.DateField('Ngày khai giảng dự kiến', null=True, blank=True)
    lich_hoc = models.CharField('Lịch học', max_length=255, null=True, blank=True, help_text='VD: Tối Thứ 2-4-6, 18:00-20:00')
    dia_diem = models.CharField('Địa điểm học', max_length=255, null=True, blank=True)
    hoc_phi = models.DecimalField('Học phí dự kiến', max_digits=12, decimal_places=0, null=True, blank=True)
    mo_ta = models.TextField('Mô tả/lưu ý', null=True, blank=True)
    trang_thai = models.BooleanField('Đang mở đăng ký', default=True)
    sinh_vien = models.ManyToManyField(SinhVien, related_name='lop_hoc', blank=True)
    file_import_excel = models.FileField('Excel nạp SV', upload_to='temp_imports/', blank=True, null=True)

    class Meta:
        verbose_name = 'Lớp bồi dưỡng'
        verbose_name_plural = '7. Quản lý Lớp bồi dưỡng'
        ordering = ['-id']

    def __str__(self):
        return f"{self.ten_lop} ({self.sinh_vien.count()}/{self.si_so_toi_da})"

    @property
    def si_so_hien_tai(self):
        return self.sinh_vien.count()

    @property
    def con_cho(self):
        return max((self.si_so_toi_da or 0) - self.si_so_hien_tai, 0)

    @property
    def da_day(self):
        return self.si_so_toi_da and self.si_so_hien_tai >= self.si_so_toi_da

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.file_import_excel:
            try:
                df = pd.read_excel(self.file_import_excel)
                if 'MSSV' in df.columns:
                    mssv_list = df['MSSV'].astype(str).str.strip().tolist()
                    sinh_viens_hop_le = SinhVien.objects.filter(mssv__in=mssv_list)
                    self.sinh_vien.add(*sinh_viens_hop_le)
            except Exception:
                pass
            self.file_import_excel.delete(save=False)
            super().save(update_fields=['file_import_excel'])


class DangKyLop(models.Model):
    TRANG_THAI_DK = [
        ('CHO_DUYET', 'Chờ duyệt'),
        ('THANH_CONG', 'Đã duyệt'),
        ('DA_HUY', 'Đã hủy'),
    ]

    sinh_vien = models.ForeignKey(SinhVien, on_delete=models.CASCADE, related_name='ds_dang_ky_lop')
    lop_hoc = models.ForeignKey(LopBoiDuong, on_delete=models.CASCADE, related_name='ds_dang_ky')
    file_minh_chung = models.FileField('Biên lai', upload_to='minh_chung_dk/%Y/%m/', blank=True, null=True)
    thoi_gian_dk = models.DateTimeField('Thời gian đăng ký', auto_now_add=True)
    trang_thai = models.CharField('Trạng thái', max_length=20, choices=TRANG_THAI_DK, default='CHO_DUYET')

    class Meta:
        verbose_name = 'Phiếu đăng ký'
        verbose_name_plural = '8. Duyệt Đăng ký học'
        unique_together = ('sinh_vien', 'lop_hoc')
        ordering = ['-thoi_gian_dk']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.trang_thai == 'THANH_CONG':
            self.lop_hoc.sinh_vien.add(self.sinh_vien)
        elif self.trang_thai in ['CHO_DUYET', 'DA_HUY']:
            self.lop_hoc.sinh_vien.remove(self.sinh_vien)




# ==============================================================================
# PHÂN HỆ 4: CHĂM SÓC SINH VIÊN, CẢNH BÁO & THÔNG BÁO
# ==============================================================================
class ThongBao(models.Model):
    LOAI_THONG_BAO = [
        ('CHUNG', 'Thông báo chung'),
        ('CANH_BAO_NN', 'Cảnh báo chuẩn Ngoại ngữ'),
        ('CANH_BAO_TH', 'Cảnh báo chuẩn Tin học'),
        ('CANH_BAO_CDR', 'Cảnh báo chuẩn đầu ra'),
        ('LOP_BOI_DUONG', 'Gợi ý lớp bồi dưỡng'),
        ('LICH_THI', 'Lịch thi/khảo thí'),
        ('TU_VAN', 'Tư vấn hỗ trợ'),
    ]

    DOI_TUONG = [
        ('ALL', 'Tất cả sinh viên'),
        ('CHUA_DAT_NN', 'Sinh viên chưa đạt Ngoại ngữ'),
        ('CHUA_DAT_TH', 'Sinh viên chưa đạt Tin học'),
        ('CHUA_DAT_CDR', 'Sinh viên chưa đạt một trong hai chuẩn'),
        ('NAM_CUOI', 'Sinh viên năm cuối/chuẩn bị tốt nghiệp'),
    ]

    loai = models.CharField('Loại thông báo', max_length=30, choices=LOAI_THONG_BAO, default='CHUNG')
    doi_tuong = models.CharField('Đối tượng nhận', max_length=30, choices=DOI_TUONG, default='ALL')
    tieu_de = models.CharField('Tiêu đề', max_length=255)
    noi_dung = models.TextField('Nội dung')
    link_url = models.CharField('Đường dẫn liên kết', max_length=500, null=True, blank=True)
    ngay_bat_dau = models.DateField('Ngày bắt đầu hiển thị', null=True, blank=True)
    ngay_ket_thuc = models.DateField('Ngày kết thúc hiển thị', null=True, blank=True)
    is_active = models.BooleanField('Đang hiển thị', default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Người tạo')
    created_at = models.DateTimeField('Ngày tạo', auto_now_add=True)
    updated_at = models.DateTimeField('Cập nhật lần cuối', auto_now=True)

    class Meta:
        verbose_name = 'Thông báo chăm sóc sinh viên'
        verbose_name_plural = '9. Chăm sóc sinh viên - Thông báo/Cảnh báo'
        ordering = ['-created_at']

    def __str__(self):
        return self.tieu_de

    def dang_hieu_luc(self):
        today = timezone.now().date()
        if not self.is_active:
            return False
        if self.ngay_bat_dau and today < self.ngay_bat_dau:
            return False
        if self.ngay_ket_thuc and today > self.ngay_ket_thuc:
            return False
        return True

    def phu_hop_voi_sinh_vien(self, sinh_vien):
        if not self.dang_hieu_luc():
            return False
        if self.doi_tuong == 'ALL':
            return True
        if self.doi_tuong == 'CHUA_DAT_NN':
            return not sinh_vien.check_dat_ngoai_ngu
        if self.doi_tuong == 'CHUA_DAT_TH':
            return not sinh_vien.check_dat_tin_hoc
        if self.doi_tuong == 'CHUA_DAT_CDR':
            return not sinh_vien.dat_chuan_dau_ra
        if self.doi_tuong == 'NAM_CUOI':
            return sinh_vien.tien_do_nam_tu
        return True


# ==============================================================================
# DỌN DẸP FILE RÁC KHI XÓA BẢN GHI
# ==============================================================================
@receiver(post_delete, sender=ChungChi)
@receiver(post_delete, sender=DangKyLop)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    field_name = 'file_minh_chung'
    if hasattr(instance, field_name):
        file = getattr(instance, field_name)
        if file and os.path.isfile(file.path):
            os.remove(file.path)
