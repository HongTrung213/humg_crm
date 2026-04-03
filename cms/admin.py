from django.contrib import admin
from .models import Category, Post,QuickLink

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # Thêm show_on_navbar vào danh sách
    list_display = ('name', 'slug', 'is_active', 'show_on_navbar')
    # Cho phép click bật/tắt trực tiếp
    list_editable = ('is_active', 'show_on_navbar') 
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at', 'is_published')
    list_filter = ('category', 'is_published', 'created_at')
    search_fields = ('title', 'summary')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(QuickLink)
class QuickLinkAdmin(admin.ModelAdmin):
    list_display = ('title', 'url', 'order', 'is_active')
    list_editable = ('order', 'is_active')

