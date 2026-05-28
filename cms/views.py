
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm, PostForm, QuickLinkForm, SliderForm
from .models import Category, Post, QuickLink, Slider


# ==========================================
# 1. PUBLIC VIEWS
# ==========================================
def post_list(request, category_slug=None):
    query = request.GET.get('q', '').strip()
    posts = Post.objects.select_related('category').filter(is_published=True, category__is_active=True)

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        posts = posts.filter(category=category)
    else:
        category = None

    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(summary__icontains=query) | Q(content__icontains=query))

    posts = posts.order_by('-created_at')
    paginator = Paginator(posts, 6)
    page_number = request.GET.get('page')
    try:
        posts_page = paginator.page(page_number)
    except PageNotAnInteger:
        posts_page = paginator.page(1)
    except EmptyPage:
        posts_page = paginator.page(paginator.num_pages)

    return render(request, 'cms/post_list.html', {
        'posts': posts_page,
        'category': category,
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'query': query,
        'quick_links': QuickLink.objects.filter(is_active=True).order_by('order'),
    })


def post_detail(request, post_slug):
    post = get_object_or_404(Post.objects.select_related('category'), slug=post_slug, is_published=True, category__is_active=True)
    Post.objects.filter(pk=post.pk).update(view_count=post.view_count + 1)
    post.view_count += 1

    related_posts = Post.objects.select_related('category').filter(
        category=post.category,
        is_published=True,
        category__is_active=True,
    ).exclude(pk=post.pk).order_by('-created_at')[:4]

    return render(request, 'cms/post_detail.html', {
        'post': post,
        'related_posts': related_posts,
        'quick_links': QuickLink.objects.filter(is_active=True).order_by('order'),
    })


# ==========================================
# 2. MOFI ADMIN VIEWS
# ==========================================
@staff_member_required
def mofi_post_list(request):
    query = request.GET.get('q', '').strip()
    posts = Post.objects.select_related('category').order_by('-created_at')
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(category__name__icontains=query))
    return render(request, 'admin_mofi/pages/post_list.html', {'posts': posts, 'query': query})


@staff_member_required
def mofi_post_add(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã đăng bài viết mới thành công!')
            return redirect('cms:mofi_post_list')
    else:
        form = PostForm()
    return render(request, 'admin_mofi/pages/post_form.html', {'form': form})


@staff_member_required
def mofi_post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật bài viết thành công!')
            return redirect('cms:mofi_post_list')
    else:
        form = PostForm(instance=post)
    return render(request, 'admin_mofi/pages/post_form.html', {'form': form, 'instance': post})


@staff_member_required
def mofi_post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    post.delete()
    messages.success(request, 'Đã xóa bài viết thành công!')
    return redirect('cms:mofi_post_list')


@staff_member_required
def mofi_category_list(request):
    query = request.GET.get('q', '').strip()
    categories = Category.objects.all().order_by('name')
    if query:
        categories = categories.filter(name__icontains=query)
    return render(request, 'admin_mofi/pages/category_list.html', {'categories': categories, 'query': query})


@staff_member_required
def mofi_category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Thêm danh mục thành công!')
            return redirect('cms:mofi_category_list')
    else:
        form = CategoryForm()
    return render(request, 'admin_mofi/pages/category_form.html', {'form': form})


@staff_member_required
def mofi_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật danh mục thành công!')
            return redirect('cms:mofi_category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'admin_mofi/pages/category_form.html', {'form': form, 'instance': category})


@staff_member_required
def mofi_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    name = category.name
    category.delete()
    messages.success(request, f'Đã xóa danh mục "{name}" thành công!')
    return redirect('cms:mofi_category_list')


@staff_member_required
def mofi_slider_list(request):
    sliders = Slider.objects.all().order_by('order')
    return render(request, 'admin_mofi/pages/slider_list.html', {'sliders': sliders})


@staff_member_required
def mofi_slider_form(request, pk=None):
    instance = get_object_or_404(Slider, pk=pk) if pk else None
    if request.method == 'POST':
        form = SliderForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật Slider thành công!')
            return redirect('cms:mofi_slider_list')
    else:
        form = SliderForm(instance=instance)
    return render(request, 'admin_mofi/pages/slider_form.html', {
        'form': form,
        'title': 'Chỉnh sửa Slider' if pk else 'Thêm Slider mới',
        'instance': instance,
    })


@staff_member_required
def mofi_slider_delete(request, pk):
    slider = get_object_or_404(Slider, pk=pk)
    slider.delete()
    messages.success(request, 'Đã xóa Slider thành công!')
    return redirect('cms:mofi_slider_list')


@staff_member_required
def mofi_quicklink_list(request):
    quicklinks = QuickLink.objects.all().order_by('order')
    return render(request, 'admin_mofi/pages/quicklink_list.html', {'quicklinks': quicklinks})


@staff_member_required
def mofi_quicklink_form(request, pk=None):
    instance = get_object_or_404(QuickLink, pk=pk) if pk else None
    if request.method == 'POST':
        form = QuickLinkForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật Liên kết nhanh thành công!')
            return redirect('cms:mofi_quicklink_list')
    else:
        form = QuickLinkForm(instance=instance)
    return render(request, 'admin_mofi/pages/quicklink_form.html', {
        'form': form,
        'title': 'Chỉnh sửa QuickLink' if pk else 'Thêm QuickLink mới',
        'instance': instance,
    })


@staff_member_required
def mofi_quicklink_delete(request, pk):
    ql = get_object_or_404(QuickLink, pk=pk)
    ql.delete()
    messages.success(request, 'Đã xóa Liên kết nhanh thành công!')
    return redirect('cms:mofi_quicklink_list')
