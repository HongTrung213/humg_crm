from django.db import models
from django.utils.text import slugify
from ckeditor.fields import RichTextField # DÒNG QUAN TRỌNG NHẤT ĐỂ SỬA LỖI ĐÂY RỒI

class Category(models.Model):
    name = models.CharField('Tên danh mục', max_length=100)
    slug = models.SlugField('Đường dẫn (Slug)', unique=True, blank=True)
    is_active = models.BooleanField('Hiển thị ở Sidebar', default=True)
    
    # BỔ SUNG TRƯỜNG NÀY
    show_on_navbar = models.BooleanField(
        'Hiển thị trên Menu chính', 
        default=False, 
        help_text='Tick vào ô này để đưa danh mục lên thanh Menu ngang trên cùng'
    )
    show_on_homepage = models.BooleanField(
        'Thành khối riêng ở Trang chủ', 
        default=False, 
        help_text='Tick vào đây để tạo thành một khối lưới 4 bài viết dưới cùng Trang chủ'
    )
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
    

class QuickLink(models.Model):
    title = models.CharField('Tên liên kết', max_length=100)
    url = models.URLField('Đường dẫn (URL)')
    
    # BỔ SUNG THÊM DÒNG NÀY ĐỂ UPLOAD ẢNH BANNER
    image = models.ImageField('Ảnh Banner', upload_to='cms/quicklinks/', blank=True, null=True, help_text='Nên dùng ảnh chữ nhật ngang (Ví dụ: 300x100px)')
    
    order = models.IntegerField('Thứ tự hiển thị', default=0, help_text='Số nhỏ hiển thị trước')
    is_active = models.BooleanField('Đang hoạt động', default=True)

    class Meta:
        verbose_name = 'Liên kết nhanh'
        verbose_name_plural = '3. Quản lý Liên kết nhanh (Sidebar)'
        ordering = ['order']

    def __str__(self):
        return self.title