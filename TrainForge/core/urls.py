from django.urls import path
from . import views

urlpatterns = [
    # Public pages
    path('', views.landing, name='landing'),
    path('auth/', views.auth_page, name='auth'),
    path('logout/', views.logout_view, name='logout'),

    # Main app pages
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),

    # Client management
    path('clients/', views.clients, name='clients'),
    path('clients/add/', views.add_client, name='add_client'),
    path('clients/generate-ai/', views.generate_client_plan_and_note, name='generate_client_plan_and_note'),
    path('clients/<int:client_id>/edit/', views.edit_client, name='edit_client'),
    path('clients/<int:client_id>/delete/', views.delete_client, name='delete_client'),

    # Training plans
    path('plans/', views.plans, name='plans'),
    path('plans/<int:client_id>/create/', views.create_plan, name='create_plan'),
    path('plans/<int:plan_id>/update/', views.update_plan, name='update_plan'),
    path('plans/<int:plan_id>/delete/', views.delete_plan, name='delete_plan'),

    # Appointments
    path('appointments/', views.appointments, name='appointments'),
    path('appointments/add/', views.add_appointment, name='add_appointment'),
    path('appointments/<int:appointment_id>/delete/', views.delete_appointment, name='delete_appointment'),

    # Progress tracking
    path('progress/', views.progress, name='progress'),
    path('progress/add/', views.add_progress_log, name='add_progress_log'),
    path('progress/<int:log_id>/edit/', views.edit_progress_log, name='edit_progress_log'),
    path('progress/<int:log_id>/delete/', views.delete_progress_log, name='delete_progress_log'),

     # Trainer subscriptions
    path('subscriptions/', views.subscriptions, name='subscriptions'),
    path('subscriptions/add/', views.add_subscription, name='add_subscription'),
    path('subscriptions/<int:subscription_id>/edit/', views.edit_subscription, name='edit_subscription'),
    path('subscriptions/<int:subscription_id>/archive/', views.archive_subscription, name='archive_subscription'),
]
