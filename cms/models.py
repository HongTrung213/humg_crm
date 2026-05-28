
import re

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def vi_slugify(text):
    """Chuyển đổi tiếng Việt có dấu thành slug chuẩn."""
    text = str(text or '').lower().strip()
    text = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', text)
    text = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', text)
    text = re.sub(r'[ìíịỉĩ]', 'i', text)
    text = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', text)
    text = re.sub(r'[ùúụủũưừứựửữ]', 'u', text)
    text = re.sub(r'[ỳýỵỷỹ]', 'y', text)
    text = re.sub(r'đ', 'd', text)
    return slugify(text)


class Category(models.Model):
    name = models.CharField(max_length=255, verbose_name='Tên danh mục')
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True, verbose_name='Đường dẫn (Slug)')
    description = models.TextField(blank=True, null=True, verbose_name='Mô tả')
    show_on_navbar = models.BooleanField(default=False, verbose_name='Hiển thị trên menu')
    show_on_homepage = models.BooleanField(default=False, verbose_name='Hiển thị trên trang chủ')
    is_active = models.BooleanField(default=True, verbose_name='Hoạt động')

    class Meta:
        verbose_name = 'Danh mục bài viết'
        verbose_name_plural = 'Danh mục bài viết'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = vi_slugify(self.name)
            slug = base_slug
            counter = 1
            qs = Category.objects.filter(slug=slug)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
                qs = Category.objects.filter(slug=slug)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Post(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='posts', verbose_name='Danh mục')
    title = models.CharField(max_length=255, verbose_name='Tiêu đề bài viết')
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True, verbose_name='Đường dẫn')
    summary = models.TextField(blank=True, null=True, verbose_name='Tóm tắt')
    content = models.TextField(verbose_name='Nội dung')
    image = models.ImageField(upload_to='bai_viet/', blank=True, null=True, verbose_name='Ảnh đại diện')
    attachment = models.FileField(upload_to='bai_viet/dinh_kem/', blank=True, null=True, verbose_name='Tài liệu đính kèm')
    view_count = models.IntegerField(default=0, verbose_name='Lượt xem')
    is_published = models.BooleanField(default=True, verbose_name='Xuất bản')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bài viết'
        verbose_name_plural = 'Bài viết'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = vi_slugify(self.title)
            slug = base_slug
            counter = 1
            qs = Post.objects.filter(slug=slug)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
                qs = Post.objects.filter(slug=slug)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('cms:post_detail', kwargs={'post_slug': self.slug})

    def __str__(self):
        return self.title


class Slider(models.Model):
    title = models.CharField(max_length=200, verbose_name='Tiêu đề Banner')
    image = models.ImageField(upload_to='cms/sliders/', verbose_name='Hình ảnh')
    link_url = models.CharField(max_length=500, blank=True, null=True, verbose_name='Link liên kết')
    order = models.IntegerField(default=0, verbose_name='Thứ tự')
    is_active = models.BooleanField(default=True, verbose_name='Hiển thị')

    class Meta:
        verbose_name = 'Slider'
        verbose_name_plural = '1. Quản lý Slider'
        ordering = ['order']

    def __str__(self):
        return self.title


class QuickLink(models.Model):
    title = models.CharField(max_length=100, verbose_name='Tên liên kết')
    image = models.ImageField(upload_to='cms/quicklinks/', verbose_name='Ảnh Banner nút')
    url = models.CharField(max_length=500, verbose_name='Đường dẫn ngoài')
    order = models.IntegerField(default=0, verbose_name='Thứ tự')
    is_active = models.BooleanField(default=True, verbose_name='Hiển thị')

    class Meta:
        verbose_name = 'Liên kết nhanh'
        verbose_name_plural = '2. Quản lý Quick Links'
        ordering = ['order']

    def __str__(self):
        return self.title
