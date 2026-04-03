"""
URL configuration for core project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Đường dẫn quản trị của Cán bộ
    path('admin/', admin.site.urls),
    
    # Đường dẫn ứng dụng Tin tức (CMS)
    path('tin-tuc/', include('cms.urls')),
    
    # Đẩy toàn bộ các đường dẫn của ứng dụng Sinh viên (bao gồm cả Trang chủ) ra thư mục gốc
    path('', include('students.urls')),
]

from django.conf import settings             # THÊM DÒNG NÀY
from django.conf.urls.static import static   # THÊM DÒNG NÀY

# THÊM ĐOẠN NÀY VÀO DƯỚI CÙNG ĐỂ HIỂN THỊ ẢNH
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)