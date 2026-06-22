from django.db.models import QuerySet

from .models import CauHinhVaiTro


GLOBAL_ROLES = {'ADMIN', 'TRUNG_TAM'}
KHOA_SCOPED_ROLES = {'KHOA', 'CO_VAN', 'GIANG_VIEN', 'PHONG_BAN'}


def get_user_role_scope(user):
    if not user or not user.is_authenticated:
        return None
    try:
        scope = user.vai_tro_nghiep_vu
    except CauHinhVaiTro.DoesNotExist:
        return None
    return scope if scope.is_active else None


def can_access_all_students(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    scope = get_user_role_scope(user)
    if not scope:
        return bool(user.is_staff)
    return scope.duoc_xem_toan_bo or scope.vai_tro in GLOBAL_ROLES


def get_student_queryset_for_user(user, queryset: QuerySet):
    if can_access_all_students(user):
        return queryset

    scope = get_user_role_scope(user)
    if not scope:
        return queryset.none()

    if scope.vai_tro in KHOA_SCOPED_ROLES:
        khoa_ids = scope.khoa_ids
        if khoa_ids:
            return queryset.filter(khoa_id__in=khoa_ids)
        return queryset.none()

    if scope.vai_tro == 'SINH_VIEN':
        return queryset.filter(user=user)

    return queryset.none()


def can_manage_student(user, student):
    if not student:
        return False
    return get_student_queryset_for_user(user, student.__class__.objects.filter(pk=student.pk)).exists()
