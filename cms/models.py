from django.db import models
from django.utils.text import slugify
from ckeditor.fields import RichTextField # DÒNG QUAN TRỌNG NHẤT ĐỂ SỬA LỖI ĐÂY RỒI

class Category(models.Model):
    name = models.CharField('Tên danh mục', max_length=100)
    slug = models.SlugField('Đường dẫn (Slug)', unique=True, blank=True)

    class Meta:
        verbose_name = 'Danh mục'
        verbose_name_plural = '1. Quản lý Danh mục'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Post(models.Model):
    title = models.CharField('Tiêu đề bài viết', max_length=200)
    slug = models.SlugField('Đường dẫn (Slug)', unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='posts', verbose_name='Danh mục')
    
    summary = models.TextField('Tóm tắt ngắn', max_length=500, help_text='Hiển thị ở trang danh sách')
    
    # Sử dụng RichTextField thay cho TextField thông thường
    content = RichTextField('Nội dung chi tiết')
    
    image = models.ImageField('Ảnh đại diện', upload_to='cms/images/%Y/%m/', blank=True, null=True)
    attachment = models.FileField('File đính kèm (PDF/Docx)', upload_to='cms/attachments/%Y/%m/', blank=True, null=True)
    
    created_at = models.DateTimeField('Ngày đăng', auto_now_add=True)
    is_published = models.BooleanField('Cho phép hiển thị', default=True)

    class Meta:
        verbose_name = 'Bài viết / Thông báo'
        verbose_name_plural = '2. Quản lý Bài viết'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title