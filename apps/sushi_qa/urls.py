# apps/sushi_qa/urls.py
from django.urls import path
from . import views

app_name = 'sushi_qa'


urlpatterns = [
    path("", views.QAPageView.as_view(), name="qa_page"),
    path("query/", views.QAQueryView.as_view(), name="qa_query"),
    path('dialogue/detail/', views.DialogueDetailView.as_view(), name='dialogue_detail'),
]
