from django.core.management.base import BaseCommand
from students.models import Khoa, DanhMucChungChi

class Command(BaseCommand):
    help = 'Khởi tạo dữ liệu danh mục gốc (Master Data) cho hệ thống HUMG CRM'

    def handle(self, *args, **kwargs):
        self.stdout.write("Đang nạp dữ liệu Master Data...")

        # 1. KHỞI TẠO 10 KHOA CHUẨN CỦA ĐẠI HỌC MỎ - ĐỊA CHẤT
        danh_sach_khoa = [
            "Công nghệ thông tin",
            "Cơ - Điện",
            "Dầu khí",
            "Khoa học Cơ bản",
            "Khoa học và Kỹ thuật Địa chất",
            "Kinh tế và Quản trị Kinh doanh",
            "Mỏ",
            "Môi trường",
            "Trắc địa - Bản đồ và Quản lý đất đai",
            "Xây dựng"
        ]
        
        count_khoa = 0
        for ten in danh_sach_khoa:
            obj, created = Khoa.objects.get_or_create(ten_khoa=ten)
            if created:
                count_khoa += 1

        # 2. KHỞI TẠO CÁC LOẠI CHỨNG CHỈ (NGOẠI NGỮ & TIN HỌC)
        danh_sach_chung_chi = [
            # ----- Nhóm Tiếng Anh -----
            {'loai': 'NGOAI_NGU', 'ten': 'TOEIC Quốc tế (Nghe - Đọc)'},
            {'loai': 'NGOAI_NGU', 'ten': 'TOEIC Quốc tế (4 Kỹ năng)'},
            {'loai': 'NGOAI_NGU', 'ten': 'IELTS Academic'},
            {'loai': 'NGOAI_NGU', 'ten': 'Aptis ESOL'},
            {'loai': 'NGOAI_NGU', 'ten': 'VSTEP (Bậc 3-5)'},
            {'loai': 'NGOAI_NGU', 'ten': 'TOEFL iBT'},
            {'loai': 'NGOAI_NGU', 'ten': 'Linguaskill'},
            
            # ----- Nhóm Ngoại ngữ khác -----
            {'loai': 'NGOAI_NGU', 'ten': 'HSK (Tiếng Trung)'},
            {'loai': 'NGOAI_NGU', 'ten': 'JLPT (Tiếng Nhật)'},
            {'loai': 'NGOAI_NGU', 'ten': 'TOPIK (Tiếng Hàn)'},

            # ----- Nhóm Tin học -----
            {'loai': 'TIN_HOC', 'ten': 'MOS (Microsoft Office Specialist)'},
            {'loai': 'TIN_HOC', 'ten': 'IC3 (Digital Literacy)'},
            {'loai': 'TIN_HOC', 'ten': 'ICDL (International Computer Driving Licence)'},
            {'loai': 'TIN_HOC', 'ten': 'Chứng chỉ Ứng dụng CNTT Cơ bản'},
            {'loai': 'TIN_HOC', 'ten': 'Chứng chỉ Ứng dụng CNTT Nâng cao'},
        ]

        count_cc = 0
        for cc in danh_sach_chung_chi:
            obj, created = DanhMucChungChi.objects.get_or_create(
                loai=cc['loai'], 
                ten_chung_chi=cc['ten']
            )
            if created:
                count_cc += 1

        # In thông báo thành công ra Terminal
        self.stdout.write(self.style.SUCCESS(f'✅ Đã nạp thành công {count_khoa} Khoa/Viện.'))
        self.stdout.write(self.style.SUCCESS(f'✅ Đã nạp thành công {count_cc} Danh mục Chứng chỉ.'))
        self.stdout.write(self.style.SUCCESS('Hệ thống đã sẵn sàng hoạt động!'))