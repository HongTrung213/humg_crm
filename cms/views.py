from django.shortcuts import render, get_object_or_404
from .models import Category, Post
from cms.models import Post

def post_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()
    posts = Post.objects.filter(is_published=True)

    # Nếu người dùng click vào 1 danh mục cụ thể, lọc bài viết theo danh mục đó
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        posts = posts.filter(category=category)

    return render(request, 'cms/post_list.html', {
        'category': category,
        'categories': categories,
        'posts': posts
    })

def post_detail(request, post_slug):
    post = get_object_or_404(Post, slug=post_slug, is_published=True)
    
    # Gợi ý 3 bài viết cùng chuyên mục để sinh viên đọc thêm
    related_posts = Post.objects.filter(category=post.category, is_published=True).exclude(id=post.id)[:3]
    categories = Category.objects.all()
    
    return render(request, 'cms/post_detail.html', {
        'post': post,
        'related_posts': related_posts,
        'categories': categories
    })