from django.db import models

class SinhVien(models.Model):
    # Thông tin định danh
    mssv = models.CharField('Mã Sinh Viên', max_length=15, unique=True)
    ho_ten = models.CharField('Họ và Tên', max_length=100)
    # Thêm null=True, blank=True để tránh lỗi khi migrate
    khoa = models.CharField('Khoa', max_length=100, null=True, blank=True)
    lop = models.CharField('Lớp', max_length=50, null=True, blank=True)
    so_dien_thoai = models.CharField('Số điện thoại', max_length=15, null=True, blank=True)
    
    # Email: Hệ thống tự sinh email trường nếu để trống
    email_truong = models.EmailField('Email trường', unique=True, null=True, blank=True)
    email_ngoai = models.EmailField('Email cá nhân', null=True, blank=True)

    # Điểm số các kỳ thi tại trường (Mặc định 0)
    diem_anh_van_dau_vao = models.FloatField('Điểm TA đầu vào', default=0)
    diem_cdr_ngoai_ngu = models.FloatField('Điểm CĐR Ngoại ngữ', default=0)
    diem_cdr_tin_hoc = models.FloatField('Điểm CĐR Tin học', default=0)

    # Trạng thái chứng chỉ ngoài (Để xét miễn thi)
    has_chung_chi_ngoai_ngu = models.BooleanField('Có chứng chỉ NN ngoài (IELTS/TOEIC...)', default=False)
    has_chung_chi_tin_hoc = models.BooleanField('Có chứng chỉ Tin học ngoài (MOS/IC3...)', default=False)
    is_mien_thi_dau_vao = models.BooleanField('Miễn thi TA đầu vào', default=False)

    class Meta:
        verbose_name = 'Sinh Viên'
        verbose_name_plural = 'Danh Sách Sinh Viên'

    def save(self, *args, **kwargs):
        # Tự động tạo email trường theo định dạng: mssv@student.humg.edu.vn
        if not self.email_truong:
            self.email_truong = f"{self.mssv}@student.humg.edu.vn"
        super(SinhVien, self).save(*args, **kwargs)

    # --- LOGIC XÉT DUYỆT (Sử dụng Property để không làm nặng Database) ---

    @property
    def check_dat_dau_vao(self):
        return self.is_mien_thi_dau_vao or self.diem_anh_van_dau_vao >= 5.0

    @property
    def check_dat_ngoai_ngu(self):
        return self.has_chung_chi_ngoai_ngu or self.diem_cdr_ngoai_ngu >= 5.0

    @property
    def check_dat_tin_hoc(self):
        return self.has_chung_chi_tin_hoc or self.diem_cdr_tin_hoc >= 5.0

    def __str__(self):
        return f"{self.mssv} - {self.ho_ten}"
# students/models.py

class LopBoiDuong(models.Model):
    ma_lop = models.CharField('Mã lớp', max_length=20, unique=True)
    ten_lop = models.CharField('Tên lớp', max_length=200)
    loai = models.CharField('Loại lớp', max_length=50, choices=[('TATC', 'Tiếng Anh tăng cường'), ('CDR', 'Chuẩn đầu ra')])
    sinh_vien = models.ManyToManyField(SinhVien, related_name='lop_hoc')

    def __str__(self):
        return self.ten_lop

class DiemThi(models.Model):
    sinh_vien = models.ForeignKey(SinhVien, on_delete=models.CASCADE)
    mon_thi = models.CharField('Môn thi', max_length=100) # Tiếng Anh / Tin học
    diem_so = models.FloatField('Điểm')
    ngay_thi = models.DateField('Ngày thi')
    is_dat = models.BooleanField('Kết quả đạt', default=False)