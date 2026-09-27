from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, AllowAny
from datetime import date, datetime, timedelta, time

from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token

from .models import Servico, Agendamento, BloqueioHorario
from .serializers import (
    ServicoSerializer, AgendamentoSerializer,
    AgendamentoCreateSerializer, BloqueioHorarioSerializer,
)

HORA_INICIO_EXPEDIENTE = time(8, 0)
HORA_FIM_EXPEDIENTE = time(19, 0)
INTERVALO_MINUTOS = 30


def minutos(t: time) -> int:
    return t.hour * 60 + t.minute


def time_from_min(m: int) -> time:
    return time(m // 60, m % 60)


def gerar_slots():
    """Retorna todos os slots do expediente em intervalos de 30 min."""
    slots = []
    cur = minutos(HORA_INICIO_EXPEDIENTE)
    fim = minutos(HORA_FIM_EXPEDIENTE)
    while cur < fim:
        slots.append(time_from_min(cur))
        cur += INTERVALO_MINUTOS
    return slots


TODOS_SLOTS = gerar_slots()


def slot_disponivel(data_ag, hora_inicio_t, duracao_min, agendamentos_qs, excluir_id=None):
    """Retorna True se o slot está livre (sem conflito e dentro do expediente)."""
    inicio = minutos(hora_inicio_t)
    fim = inicio + duracao_min
    if fim > minutos(HORA_FIM_EXPEDIENTE):
        return False

    qs = agendamentos_qs.filter(data=data_ag).exclude(status='cancelado')
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)

    for ag in qs:
        ag_ini = minutos(ag.hora_inicio)
        ag_fim = minutos(ag.hora_fim)
        if inicio < ag_fim and fim > ag_ini:
            return False
    return True


# ─── PÚBLICO ─────────────────────────────────────────────────────────────────

class ServicosView(APIView):
    """Lista todos os serviços ativos, agrupados por categoria."""
    permission_classes = [AllowAny]

    def get(self, request):
        servicos = Servico.objects.filter(ativo=True)
        serializer = ServicoSerializer(servicos, many=True)
        return Response(serializer.data)


class HorariosDisponiveisView(APIView):
    """
    Lista os horários disponíveis para um dia e duração total.

    Query params:
        data       — YYYY-MM-DD  (obrigatório)
        servico_id — int         (obrigatório)
        servico_adicional_id — int (opcional)

    Lógica de encaixe:
    Quando o serviço principal dura >= 3h, também retorna os slots livres
    DENTRO do bloco ocupado por esse serviço, para permitir que o cabeleireiro
    atenda clientes com serviços curtos (30 min) enquanto aguarda.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        data_str = request.query_params.get('data')
        servico_id = request.query_params.get('servico_id')
        servico_adicional_id = request.query_params.get('servico_adicional_id')

        if not data_str or not servico_id:
            return Response({'erro': 'Parâmetros data e servico_id são obrigatórios.'}, status=400)

        try:
            data = date.fromisoformat(data_str)
        except ValueError:
            return Response({'erro': 'Formato de data inválido. Use YYYY-MM-DD.'}, status=400)

        try:
            servico = Servico.objects.get(id=servico_id, ativo=True)
        except Servico.DoesNotExist:
            return Response({'erro': 'Serviço não encontrado.'}, status=404)

        duracao = servico.duracao_minutos
        if servico_adicional_id:
            try:
                sa = Servico.objects.get(id=servico_adicional_id, ativo=True)
                duracao += sa.duracao_minutos
            except Servico.DoesNotExist:
                return Response({'erro': 'Serviço adicional não encontrado.'}, status=404)

        agendamentos_qs = Agendamento.objects.all()
        bloqueios_dia = set(
            BloqueioHorario.objects.filter(data=data).values_list('hora', flat=True)
        )

        slots = []
        for slot_t in TODOS_SLOTS:
            disponivel = (
                slot_disponivel(data, slot_t, duracao, agendamentos_qs)
                and slot_t not in bloqueios_dia
            )
            slots.append({
                'hora': slot_t.strftime('%H:%M'),
                'disponivel': disponivel,
            })

        return Response(slots)


class DiasDisponiveisView(APIView):
    """
    Retorna todos os dias de um mês indicando se há pelo menos um slot livre.

    Query params: ano, mes, servico_id, servico_adicional_id (opcional)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            ano = int(request.query_params.get('ano', date.today().year))
            mes = int(request.query_params.get('mes', date.today().month))
            servico_id = int(request.query_params.get('servico_id', 0))
        except (ValueError, TypeError):
            return Response({'erro': 'Parâmetros inválidos.'}, status=400)

        duracao = 30
        if servico_id:
            try:
                s = Servico.objects.get(id=servico_id, ativo=True)
                duracao = s.duracao_minutos
            except Servico.DoesNotExist:
                pass

        servico_adicional_id = request.query_params.get('servico_adicional_id')
        if servico_adicional_id:
            try:
                sa = Servico.objects.get(id=int(servico_adicional_id), ativo=True)
                duracao += sa.duracao_minutos
            except Servico.DoesNotExist:
                pass

        primeiro_dia = date(ano, mes, 1)
        if mes == 12:
            ultimo_dia = date(ano, 12, 31)
        else:
            ultimo_dia = date(ano, mes + 1, 1) - timedelta(days=1)

        hoje = date.today()
        agendamentos_qs = Agendamento.objects.all()

        resultado = []
        dia_atual = primeiro_dia
        while dia_atual <= ultimo_dia:
            if dia_atual < hoje or dia_atual.weekday() == 6:  # domingo fechado
                resultado.append({'data': dia_atual.isoformat(), 'disponivel': False})
            else:
                bloqueios_dia = set(
                    BloqueioHorario.objects.filter(data=dia_atual).values_list('hora', flat=True)
                )
                tem_slot = any(
                    slot_disponivel(dia_atual, t, duracao, agendamentos_qs)
                    and t not in bloqueios_dia
                    for t in TODOS_SLOTS
                )
                resultado.append({'data': dia_atual.isoformat(), 'disponivel': tem_slot})
            dia_atual += timedelta(days=1)

        return Response(resultado)


class AgendamentoCreateView(APIView):
    """Cria um novo agendamento (público)."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AgendamentoCreateSerializer(data=request.data)
        if serializer.is_valid():
            agendamento = serializer.save()
            return Response(AgendamentoSerializer(agendamento).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── ADMIN ────────────────────────────────────────────────────────────────────

class AgendamentosAdminView(APIView):
    """Lista todos os agendamentos (admin)."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        data_str = request.query_params.get('data')
        qs = Agendamento.objects.select_related('servico', 'servico_adicional').all()
        if data_str:
            qs = qs.filter(data=data_str)
        serializer = AgendamentoSerializer(qs, many=True)
        return Response(serializer.data)

    def patch(self, request, pk=None):
        """Atualiza status de um agendamento."""
        try:
            ag = Agendamento.objects.get(pk=pk)
        except Agendamento.DoesNotExist:
            return Response({'erro': 'Agendamento não encontrado.'}, status=404)
        novo_status = request.data.get('status')
        if novo_status not in dict(Agendamento.STATUS_CHOICES):
            return Response({'erro': 'Status inválido.'}, status=400)
        ag.status = novo_status
        ag.save()
        return Response(AgendamentoSerializer(ag).data)


class BloqueioHorarioView(APIView):
    """Gerencia bloqueios de horários (admin)."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        data_str = request.query_params.get('data')
        qs = BloqueioHorario.objects.all()
        if data_str:
            qs = qs.filter(data=data_str)
        serializer = BloqueioHorarioSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = BloqueioHorarioSerializer(data=request.data)
        if serializer.is_valid():
            b = serializer.save()
            return Response(BloqueioHorarioSerializer(b).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        try:
            b = BloqueioHorario.objects.get(pk=pk)
        except BloqueioHorario.DoesNotExist:
            return Response({'erro': 'Bloqueio não encontrado.'}, status=404)
        b.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SlotsEncaixeView(APIView):
    """
    Retorna os slots de 30 min disponíveis DENTRO de um agendamento longo (>= 3h),
    para que o admin possa encaixar clientes com serviços rápidos.

    Query params: agendamento_id
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        ag_id = request.query_params.get('agendamento_id')
        try:
            ag = Agendamento.objects.get(pk=ag_id)
        except Agendamento.DoesNotExist:
            return Response({'erro': 'Agendamento não encontrado.'}, status=404)

        duracao = minutos(ag.hora_fim) - minutos(ag.hora_inicio)
        if duracao < 180:
            return Response({'slots': [], 'mensagem': 'Agendamento não tem duração suficiente para encaixe.'})

        agendamentos_qs = Agendamento.objects.all()
        bloqueios_dia = set(
            BloqueioHorario.objects.filter(data=ag.data).values_list('hora', flat=True)
        )

        slots_livres = []
        cur = minutos(ag.hora_inicio)
        fim_ag = minutos(ag.hora_fim)
        while cur + 30 <= fim_ag:
            t = time_from_min(cur)
            if slot_disponivel(ag.data, t, 30, agendamentos_qs, excluir_id=ag.id,) and t not in bloqueios_dia:
                slots_livres.append(t.strftime('%H:%M'))
            cur += INTERVALO_MINUTOS

        return Response({'slots': slots_livres, 'agendamento_id': ag_id})

class AgendamentosClienteView(APIView):
    """Busca agendamentos de um cliente pelo nome e telefone."""
    permission_classes = [AllowAny]
 
    def get(self, request):
        nome = request.query_params.get('nome', '').strip()
        telefone = request.query_params.get('telefone', '').strip()
 
        if not nome or not telefone:
            return Response(
                {'erro': 'Os parâmetros nome e telefone são obrigatórios.'},
                status=400
            )
 
        # Busca case-insensitive e telefone normalizado (só dígitos)
        telefone_limpo = ''.join(filter(str.isdigit, telefone))
 
        qs = Agendamento.objects.select_related('servico', 'servico_adicional').filter(
            cliente_nome__iexact=nome,
        )
 
        # Filtra pelo telefone comparando apenas dígitos
        ids_match = [
            ag.pk for ag in qs
            if ''.join(filter(str.isdigit, ag.cliente_telefone)) == telefone_limpo
        ]
 
        if not ids_match:
            return Response(
                {'erro': 'Nenhuma conta encontrada com esses dados. Verifique o nome e o telefone.'},
                status=404
            )
 
        agendamentos = Agendamento.objects.select_related(
            'servico', 'servico_adicional'
        ).filter(pk__in=ids_match).order_by('data', 'hora_inicio')
 
        ativos = agendamentos.filter(status='confirmado')
        historico = agendamentos.exclude(status='confirmado').order_by('-data', '-hora_inicio')
 
        return Response({
            'cliente_nome': nome,
            'cliente_telefone': telefone,
            'ativos': AgendamentoSerializer(ativos, many=True).data,
            'historico': AgendamentoSerializer(historico, many=True).data,
        })


class AdminLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"erro": "Usuário e senha são obrigatórios."},
                status=400,
            )

        user = authenticate(
            request=request,
            username=username,
            password=password,
        )

        if not user or not user.is_staff:
            return Response(
                {"erro": "Credenciais inválidas."},
                status=401,
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "usuario": user.get_username(),
        })    
   