
from django import forms
from ckeditor.widgets import CKEditorWidget

from .models import Category, Post, QuickLink, Slider


class PostForm(forms.ModelForm):
    content = forms.CharField(widget=CKEditorWidget(), label='Nội dung chi tiết')

    class Meta:
        model = Post
        fields = ['title', 'category', 'summary', 'content', 'image', 'attachment', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tiêu đề bài viết...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Viết tóm tắt ngắn...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx,.xls,.xlsx'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'show_on_navbar', 'show_on_homepage', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'show_on_navbar': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'show_on_homepage': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


class SliderForm(forms.ModelForm):
    class Meta:
        model = Slider
        fields = ['title', 'image', 'link_url', 'order', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Chào mừng tân sinh viên...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'link_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


class QuickLinkForm(forms.ModelForm):
    class Meta:
        model = QuickLink
        fields = ['title', 'image', 'url', 'order', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VD: Cổng thông tin...'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }
