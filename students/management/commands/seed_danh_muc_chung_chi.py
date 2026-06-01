from django.core.management.base import BaseCommand

from students.models import DanhMucChungChi


class Command(BaseCommand):
    help = 'Khởi tạo danh mục chứng chỉ ngoại ngữ và tin học thường dùng để xét chuẩn đầu ra.'

    NGOAI_NGU = [
        'VSTEP',
        'APTIS',
        'IELTS',
        'TOEFL iBT',
        'TOEFL ITP',
        'TOEIC 4 kỹ năng',
        'Cambridge English',
        'HSK',
        'HSKK',
        'TOCFL',
        'JLPT',
        'NAT-TEST',
        'TOPIK',
        'DELF/DALF',
        'TCF',
        'TestDaF',
    ]

    TIN_HOC = [
        'Ứng dụng CNTT cơ bản',
        'Ứng dụng CNTT nâng cao',
        'IC3',
        'MOS Word',
        'MOS Excel',
        'MOS PowerPoint',
    ]

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for ten in self.NGOAI_NGU:
            _, is_created = DanhMucChungChi.objects.update_or_create(
                ten_chung_chi=ten,
                defaults={'loai': 'NGOAI_NGU'},
            )
            created += int(is_created)
            updated += int(not is_created)

        for ten in self.TIN_HOC:
            _, is_created = DanhMucChungChi.objects.update_or_create(
                ten_chung_chi=ten,
                defaults={'loai': 'TIN_HOC'},
            )
            created += int(is_created)
            updated += int(not is_created)

        self.stdout.write(self.style.SUCCESS(
            f'Hoàn tất khởi tạo danh mục chứng chỉ. Tạo mới: {created}, cập nhật: {updated}.'
        ))
