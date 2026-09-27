from django.urls import path
from . import views

urlpatterns = [
    # ── Público (cliente) ─────────────────────────────────────────────────────
    path('servicos/', views.ServicosView.as_view(), name='servicos'),
    path('dias-disponiveis/', views.DiasDisponiveisView.as_view(), name='dias-disponiveis'),
    path('horarios-disponiveis/', views.HorariosDisponiveisView.as_view(), name='horarios-disponiveis'),
    path('agendamentos/', views.AgendamentoCreateView.as_view(), name='agendamento-create'),
    path('agendamentos/cliente/', views.AgendamentosClienteView.as_view(), name='agendamentos-cliente'),

    # ── Admin ─────────────────────────────────────────────────────────────────
    path(
        'admin/login/',
        views.AdminLoginView.as_view(),
        name='admin-login',
    ),
    path(
        'admin/agendamentos/',
        views.AgendamentosAdminView.as_view(),
        name='admin-agendamentos',
    ),
    path(
        'admin/agendamentos/<int:pk>/',
        views.AgendamentosAdminView.as_view(),
        name='admin-agendamento-detail',
    ),
    path(
        'admin/bloqueios/',
        views.BloqueioHorarioView.as_view(),
        name='admin-bloqueios',
    ),
    path(
        'admin/bloqueios/<int:pk>/',
        views.BloqueioHorarioView.as_view(),
        name='admin-bloqueio-detail',
    ),
    path(
        'admin/slots-encaixe/',
        views.SlotsEncaixeView.as_view(),
        name='admin-slots-encaixe',
    ),
]