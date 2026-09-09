# apps/accounts/decorators.py
from django.shortcuts import redirect
from django.http import HttpResponseForbidden

def admin_required(view_func):
    """装饰器：仅允许管理员访问"""
    def wrapper(request, *args, **kwargs):
        if request.session.get('user_type') == 1:  # 1表示管理员
            return view_func(request, *args, **kwargs)
        elif not request.session.get('user_id'):
            # 未登录：跳转到管理员登录页
            return redirect('accounts:admin_login')
        else:
            # 已登录但不是管理员：拒绝访问
            return HttpResponseForbidden("您没有管理员权限")
    return wrapper