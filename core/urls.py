"""
URL configuration for core project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Đường dẫn quản trị mặc định của Django
    path('admin/', admin.site.urls),
    
    # CMS (Tin tức)
    path('tin-tuc/', include('cms.urls')),
    
    # SSO Microsoft (Đăng nhập bằng Email trường)
    path('oauth/', include('social_django.urls', namespace='social')),
    
    # Students (Bao gồm Trang chủ và Admin Mofi) - Đặt dưới cùng
    path('', include('students.urls')),
]

# Cấu hình phục vụ file Media (Ảnh, tài liệu) trong môi trường Development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)