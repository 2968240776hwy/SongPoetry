# forms.py
from django import forms
from .models import User
import re


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=16, min_length=3, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(min_length=6, max_length=20, required=True)
    password_confirm = forms.CharField(required=True)

    def clean_username(self):
        username = self.cleaned_data.get('username')
        # 验证用户名格式（字母/数字/下划线）
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise forms.ValidationError('用户名只能包含字母、数字和下划线')
        # 检查用户名是否已存在
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('用户名已存在')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('邮箱已被注册')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        # 验证密码是否包含字母和数字
        if password and (not re.search(r'[a-zA-Z]', password) or not re.search(r'[0-9]', password)):
            self.add_error('password', '密码必须包含字母和数字')

        # 验证两次密码是否一致
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', '两次输入的密码不一致')

        return cleaned_data


class LoginForm(forms.Form):
    username = forms.CharField(required=True)
    password = forms.CharField(required=True)