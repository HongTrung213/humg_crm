# students/migrations/000X_load_initial_certificates.py
from django.db import migrations

def create_initial_chungchi(apps, schema_editor):
    DanhMucChungChi = apps.get_model('students', 'DanhMucChungChi')
    chungchi_list = [
        # ===== TIẾNG ANH - BẬC 3 =====
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'IELTS 4.5 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEIC L&R 450-520 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEIC S&W 190-239 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEFL ITP 450-484 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEFL IBT 45-50 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'PET 70-80 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'APTIS 102-120 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'VSTEP Bậc 3', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'HSK cấp 3 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOPIK II cấp 3 (Bậc 3)', 'bac': 3},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'JLPT N3 (Bậc 3)', 'bac': 3},
        
        # ===== TIẾNG ANH - BẬC 4 =====
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'IELTS 5.5-6.0 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEIC L&R 600-725 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEIC S&W 270-289 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEFL ITP 500-560 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEFL IBT 61-78 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'APTIS 153-169 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'Cambridge B2 First (FCE) 160-170 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'VSTEP Bậc 4', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'HSK cấp 4 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOPIK II cấp 4 (Bậc 4)', 'bac': 4},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'JLPT N2 (Bậc 4)', 'bac': 4},
        
        # ===== TIẾNG ANH - BẬC 5 =====
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'IELTS 6.5-7.5 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEIC L&R 730-845 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEIC S&W 290-325 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEFL ITP 565-585 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEFL IBT 79-89 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'APTIS 170-183 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'Cambridge C1 Advanced 171-179 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'VSTEP Bậc 5', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'HSK cấp 5 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOPIK II cấp 5 (Bậc 5)', 'bac': 5},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'JLPT N1 (Bậc 5)', 'bac': 5},
        
        # ===== TIẾNG ANH - BẬC 6 =====
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'IELTS 8.0+ (Bậc 6)', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEIC L&R 850+ (Bậc 6)', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEIC S&W 330+ (Bậc 6)', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEFL ITP 590+ (Bậc 6)', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOEFL IBT 90+ (Bậc 6)', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'APTIS 184+ (Bậc 6)', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'Cambridge C1 Advanced 180+ (Bậc 6)', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'VSTEP Bậc 6', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'HSK cấp 6 (Bậc 6)', 'bac': 6},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOPIK II cấp 6 (Bậc 6)', 'bac': 6},
        
        # ===== TIẾNG TRUNG - BẬC 1, 2 (không bắt buộc nhưng có thể có) =====
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'HSK cấp 1 (Bậc 1)', 'bac': 1},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'HSK cấp 2 (Bậc 2)', 'bac': 2},
        
        # ===== TIẾNG NHẬT - BẬC 1, 2 =====
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'JLPT N5 (Bậc 1)', 'bac': 1},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'JLPT N4 (Bậc 2)', 'bac': 2},
        
        # ===== TIẾNG HÀN - BẬC 1, 2 =====
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOPIK I cấp 1 (Bậc 1)', 'bac': 1},
        {'loai': 'NGOAI_NGU', 'ten_chung_chi': 'TOPIK I cấp 2 (Bậc 2)', 'bac': 2},
    ]
    for item in chungchi_list:
        DanhMucChungChi.objects.get_or_create(
            ten_chung_chi=item['ten_chung_chi'],
            defaults={'loai': item['loai'], 'bac': item['bac']}
        )

def remove_initial_chungchi(apps, schema_editor):
    DanhMucChungChi = apps.get_model('students', 'DanhMucChungChi')
    names = [
        'IELTS 4.5 (Bậc 3)', 'TOEIC L&R 450-520 (Bậc 3)', 'TOEIC S&W 190-239 (Bậc 3)',
        'TOEFL ITP 450-484 (Bậc 3)', 'TOEFL IBT 45-50 (Bậc 3)', 'PET 70-80 (Bậc 3)',
        'APTIS 102-120 (Bậc 3)', 'VSTEP Bậc 3',
        'IELTS 5.5-6.0 (Bậc 4)', 'TOEIC L&R 600-725 (Bậc 4)', 'TOEIC S&W 270-289 (Bậc 4)',
        'TOEFL ITP 500-560 (Bậc 4)', 'TOEFL IBT 61-78 (Bậc 4)', 'APTIS 153-169 (Bậc 4)',
        'Cambridge B2 First (FCE) 160-170 (Bậc 4)', 'VSTEP Bậc 4',
        'IELTS 6.5-7.5 (Bậc 5)', 'TOEIC L&R 730-845 (Bậc 5)', 'TOEIC S&W 290-325 (Bậc 5)',
        'TOEFL ITP 565-585 (Bậc 5)', 'TOEFL IBT 79-89 (Bậc 5)', 'APTIS 170-183 (Bậc 5)',
        'Cambridge C1 Advanced 171-179 (Bậc 5)', 'VSTEP Bậc 5',
        'IELTS 8.0+ (Bậc 6)', 'TOEIC L&R 850+ (Bậc 6)', 'TOEIC S&W 330+ (Bậc 6)',
        'TOEFL ITP 590+ (Bậc 6)', 'TOEFL IBT 90+ (Bậc 6)', 'APTIS 184+ (Bậc 6)',
        'Cambridge C1 Advanced 180+ (Bậc 6)', 'VSTEP Bậc 6',
        'HSK cấp 1 (Bậc 1)', 'HSK cấp 2 (Bậc 2)', 'HSK cấp 3 (Bậc 3)',
        'HSK cấp 4 (Bậc 4)', 'HSK cấp 5 (Bậc 5)', 'HSK cấp 6 (Bậc 6)',
        'JLPT N5 (Bậc 1)', 'JLPT N4 (Bậc 2)', 'JLPT N3 (Bậc 3)',
        'JLPT N2 (Bậc 4)', 'JLPT N1 (Bậc 5)',
        'TOPIK I cấp 1 (Bậc 1)', 'TOPIK I cấp 2 (Bậc 2)',
        'TOPIK II cấp 3 (Bậc 3)', 'TOPIK II cấp 4 (Bậc 4)',
        'TOPIK II cấp 5 (Bậc 5)', 'TOPIK II cấp 6 (Bậc 6)',
    ]
    DanhMucChungChi.objects.filter(ten_chung_chi__in=names, loai='NGOAI_NGU').delete()

class Migration(migrations.Migration):
    dependencies = [
        ('students', '0004_add_bac_to_danhmuchungchi')
    ]
    operations = [
        migrations.RunPython(create_initial_chungchi, remove_initial_chungchi),
    ]