from django.contrib import admin
from .models import Category, Post, QuickLink, Slider

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'show_on_navbar', 'is_active')
    list_editable = ('show_on_navbar', 'is_active')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_published', 'created_at')
    list_editable = ('is_published',)
    list_filter = ('category', 'is_published')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'content')

@admin.register(QuickLink)
class QuickLinkAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active')
    list_editable = ('order', 'is_active')

@admin.register(Slider)
class SliderAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('title',)