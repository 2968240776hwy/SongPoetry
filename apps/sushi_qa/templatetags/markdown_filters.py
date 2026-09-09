# sushi_qa/templatetags/markdown_filters.py
import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()  # 注册过滤器，让模板能调用


@register.filter(name="render_markdown")  # 过滤器名：render_markdown（后续模板用）
def render_markdown(text):
    """
    将Markdown文本转为HTML
    支持：代码高亮、表格、列表、加粗/斜体、引用等常用格式
    """
    if not text:  # 处理空结果
        return ""

    # 配置Markdown扩展（覆盖主流场景）
    html_content = markdown.markdown(
        text,
        extensions=[
            "extra",  # 基础扩展（支持加粗**、斜体*、列表-等）
            "codehilite",  # 代码高亮（配合highlight.js）
            "tables",  # 表格支持（|表头|内容|格式）
            "fenced_code",  # 代码块支持（```python ... ```格式）
            "toc"  # 可选：支持目录生成（如果结果有标题）
        ],
        safe_mode=False,  # 关闭安全模式（因为我们用mark_safe手动标记安全）
        enable_attributes=False
    )

    # 标记为安全HTML，避免Django自动转义（否则会显示原始HTML标签）
    return mark_safe(html_content)