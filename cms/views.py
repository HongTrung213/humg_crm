from django.shortcuts import render, get_object_or_404
from .models import Category, Post

def post_list(request, category_slug=None):
    category = None
    posts = Post.objects.filter(is_published=True)

    if category_slug:
        # Vẫn giữ is_active=True ở đây để làm "lớp khiên" bảo mật. 
        # Nếu Admin tắt danh mục, gõ link trực tiếp vẫn sẽ báo lỗi 404.
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        posts = posts.filter(category=category)

    return render(request, 'cms/post_list.html', {
        'category': category,
        'posts': posts
        # ĐÃ XÓA biến 'categories' ở đây
    })

def post_detail(request, post_slug):
    post = get_object_or_404(Post, slug=post_slug, is_published=True)
    
    # Giữ lại bài viết liên quan (cùng chuyên mục) để sinh viên đọc tiếp
    related_posts = Post.objects.filter(category=post.category, is_published=True, category__is_active=True).exclude(id=post.id)[:3]
    
    return render(request, 'cms/post_detail.html', {
        'post': post,
        'related_posts': related_posts
        # ĐÃ XÓA biến 'categories' ở đây
    })