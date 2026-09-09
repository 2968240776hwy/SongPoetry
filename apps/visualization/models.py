from django.db import models


# Create your models here.
class userinfo(models.Model):
    uid = models.CharField(max_length=10, primary_key=True, unique=True, default='', verbose_name="用户名")
    password = models.CharField(max_length=8, verbose_name="密码")
    email = models.CharField(max_length=20, verbose_name="邮箱")
    age = models.IntegerField(default=18, verbose_name="年龄")

    class Meta:
        verbose_name_plural = '用户信息表'


class ci(models.Model):
    value = models.AutoField(primary_key=True, unique=True, verbose_name="编号")
    rhythmic = models.CharField(max_length=20, verbose_name="词牌名")
    author = models.CharField(max_length=20, verbose_name="作者")
    content = models.TextField(verbose_name="内容")

    class Meta:
        verbose_name_plural = '词牌名表'


class ciauthor(models.Model):
    value = models.AutoField(primary_key=True, unique=True, verbose_name="编号")
    name = models.CharField(max_length=20, verbose_name="作者")
    long_desc = models.TextField(verbose_name="作者介绍")
    short_desc = models.TextField(verbose_name="作者简介")

    class Meta:
        verbose_name_plural = '作者表'
