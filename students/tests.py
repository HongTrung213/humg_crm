from django.contrib.auth.models import User
from django.test import TestCase

from .models import CauHinhVaiTro, Khoa, NganhDaoTao, SinhVien, TieuChiChuanDauRa
from .permissions import can_access_all_students, get_student_queryset_for_user


class GraduationCriteriaConfigTests(TestCase):
    def setUp(self):
        self.khoa = Khoa.objects.create(ma_khoa='105', ten_khoa='Khoa CNTT')
        self.nganh = NganhDaoTao.objects.create(
            khoa=self.khoa,
            ten_nganh='Công nghệ thông tin',
            loai_nganh='THUONG',
            thoi_gian_dao_tao_nam=4.0,
        )
        self.sinh_vien = SinhVien.objects.create(
            mssv='2521050001',
            ho_ten='Nguyen Van A',
            khoa=self.khoa,
            nganh_dao_tao=self.nganh,
            khoa_tuyen_sinh=70,
            chuong_trinh_dao_tao='CHAT_LUONG_CAO',
        )

    def test_foreign_language_level_uses_config_when_available(self):
        TieuChiChuanDauRa.objects.create(
            ten_tieu_chi='CLC bac 5',
            loai_chuan='NGOAI_NGU',
            pham_vi_chuong_trinh='CHAT_LUONG_CAO',
            bac_ngoai_ngu_toi_thieu=5,
            uu_tien=1,
        )

        self.assertEqual(self.sinh_vien.get_required_foreign_language_level(), 5)

    def test_default_foreign_language_level_kept_without_config(self):
        self.assertEqual(self.sinh_vien.get_required_foreign_language_level(), 4)


class RoleScopePermissionTests(TestCase):
    def setUp(self):
        self.khoa_cntt = Khoa.objects.create(ma_khoa='105', ten_khoa='Khoa CNTT')
        self.khoa_mo = Khoa.objects.create(ma_khoa='104', ten_khoa='Khoa Mỏ')
        self.user = User.objects.create_user(username='manager', password='secret')
        self.scope = CauHinhVaiTro.objects.create(user=self.user, vai_tro='KHOA')
        self.scope.khoas_phu_trach.add(self.khoa_cntt)

        self.sv_cntt = SinhVien.objects.create(
            mssv='2521050002',
            ho_ten='SV CNTT',
            khoa=self.khoa_cntt,
        )
        self.sv_mo = SinhVien.objects.create(
            mssv='2521040003',
            ho_ten='SV Mỏ',
            khoa=self.khoa_mo,
        )

    def test_scope_filters_students_by_assigned_khoa(self):
        qs = get_student_queryset_for_user(self.user, SinhVien.objects.all())
        self.assertQuerysetEqual(qs.order_by('mssv'), [self.sv_cntt], transform=lambda x: x)

    def test_global_role_can_access_all_students(self):
        admin_user = User.objects.create_user(username='admin-scope', password='secret')
        CauHinhVaiTro.objects.create(user=admin_user, vai_tro='ADMIN')
        self.assertTrue(can_access_all_students(admin_user))
