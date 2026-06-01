from django.core.management.base import BaseCommand

from students.models import Khoa, NganhDaoTao


DEFAULT_KHOA_BY_CODE = {
    '100': 'Khoa Khoa học cơ bản',
    '101': 'Khoa Dầu khí',
    '102': 'Khoa Địa chất',
    '103': 'Khoa Trắc địa - Bản đồ và Quản lý đất đai',
    '104': 'Khoa Mỏ',
    '105': 'Khoa Công nghệ thông tin',
    '106': 'Khoa Cơ - Điện',
    '107': 'Khoa Xây dựng',
    '108': 'Khoa Môi trường',
    '401': 'Khoa Kinh tế - Quản trị kinh doanh',
}

DEFAULT_NGANH_BY_KHOA = {
    '100': [
        'Ngôn ngữ Anh',
        'Ngôn ngữ Trung Quốc',
        'Hóa dược',
        'Kỹ thuật vật liệu',
    ],
    '101': [
        'Kỹ thuật dầu khí',
        'Công nghệ kỹ thuật hoá học',
        'Kỹ thuật hoá học Chương trình tiên tiến',
        'Kỹ thuật địa vật lý',
        'Quản lý dữ liệu khoa học trái đất',
        'Công nghệ số trong thăm dò và khai thác tài nguyên thiên nhiên',
    ],
    '102': [
        'Du lịch địa chất',
        'Kỹ thuật địa chất',
        'Địa kỹ thuật xây dựng',
        'Quản lý đô thị và công trình',
        'Địa chất học',
        'Kỹ thuật Tài nguyên nước',
        'Đá quý Đá mỹ nghệ',
        'Quản lý tài nguyên khoáng sản',
    ],
    '103': [
        'Quản lý đất đai',
        'Quản lý phát triển đô thị và bất động sản',
        'Địa tin học',
        'Kỹ thuật trắc địa - bản đồ',
        'Kỹ thuật không gian',
    ],
    '104': [
        'Kỹ thuật mỏ',
        'An toàn, Vệ sinh lao động',
        'Kỹ thuật tuyển khoáng',
    ],
    '105': [
        'Công nghệ thông tin',
        'Khoa học dữ liệu',
    ],
    '106': [
        'Kỹ thuật điện',
        'Kỹ thuật cơ khí',
        'Kỹ thuật cơ khí động lực',
        'Kỹ thuật Ô tô',
        'Kỹ thuật cơ điện tử',
        'Kỹ thuật điều khiển và tự động hoá',
        'Kỹ thuật Robot',
        'Công nghệ Kỹ thuật điện, điện tử',
    ],
    '107': [
        'Kỹ thuật xây dựng',
        'Kỹ thuật xây dựng công trình giao thông',
        'Quản lý xây dựng',
        'Xây dựng công trình ngầm thành phố và Hệ thống tàu điện ngầm',
    ],
    '108': [
        'Quản lý tài nguyên và môi trường',
        'Kỹ thuật môi trường',
    ],
    '401': [
        'Quản trị kinh doanh',
        'Kế toán',
        'Quản lý công nghiệp',
        'Tài chính – Ngân hàng',
    ],
}


def detect_loai_nganh(ten_nganh: str) -> str:
    text = (ten_nganh or '').lower()
    if 'ngôn ngữ anh' in text or 'ngon ngu anh' in text:
        return 'NGON_NGU_ANH'
    if 'ngôn ngữ trung' in text or 'ngon ngu trung' in text or 'trung quốc' in text or 'trung quoc' in text:
        return 'NGON_NGU_TRUNG'
    return 'THUONG'


class Command(BaseCommand):
    help = 'Khởi tạo/sửa lại danh mục Khoa và Ngành đào tạo HUMG theo file Office 365 mẫu.'

    def handle(self, *args, **options):
        created_khoa = 0
        updated_khoa = 0
        created_nganh = 0
        updated_nganh = 0

        for ma_khoa, ten_khoa in DEFAULT_KHOA_BY_CODE.items():
            khoa, is_created = Khoa.objects.get_or_create(
                ma_khoa=ma_khoa,
                defaults={'ten_khoa': ten_khoa},
            )
            created_khoa += int(is_created)

            # Chỉ sửa khi đang là dữ liệu placeholder hoặc tên trống.
            if not is_created and (
                not khoa.ten_khoa
                or khoa.ten_khoa.strip().lower() == f'khoa mã {ma_khoa}'.lower()
            ):
                khoa.ten_khoa = ten_khoa
                khoa.save(update_fields=['ten_khoa'])
                updated_khoa += 1

            for ten_nganh in DEFAULT_NGANH_BY_KHOA.get(ma_khoa, []):
                loai_nganh = detect_loai_nganh(ten_nganh)
                nganh, nganh_created = NganhDaoTao.objects.get_or_create(
                    khoa=khoa,
                    ten_nganh=ten_nganh,
                    defaults={
                        'loai_nganh': loai_nganh,
                        'is_active': True,
                    },
                )
                created_nganh += int(nganh_created)

                changed = False
                if nganh.loai_nganh != loai_nganh:
                    nganh.loai_nganh = loai_nganh
                    changed = True
                if not nganh.is_active:
                    nganh.is_active = True
                    changed = True
                if changed:
                    nganh.save(update_fields=['loai_nganh', 'is_active'])
                    updated_nganh += 1

        self.stdout.write(self.style.SUCCESS(
            f'Hoàn tất seed Khoa/Ngành. '
            f'Khoa tạo mới: {created_khoa}, Khoa sửa tên placeholder: {updated_khoa}, '
            f'Ngành tạo mới: {created_nganh}, Ngành cập nhật: {updated_nganh}.'
        ))
