from rest_framework import serializers
from datetime import datetime, timedelta, time
from .models import Servico, Agendamento, BloqueioHorario


def minutos(t: time) -> int:
    return t.hour * 60 + t.minute


def time_from_min(m: int) -> time:
    return time(m // 60, m % 60)


HORA_FIM_EXPEDIENTE = time(19, 0)


class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = ['id', 'nome', 'categoria', 'duracao_minutos', 'ativo']


class BloqueioHorarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloqueioHorario
        fields = ['id', 'data', 'hora', 'motivo', 'criado_em']
        read_only_fields = ['id', 'criado_em']


class AgendamentoSerializer(serializers.ModelSerializer):
    servico_nome = serializers.CharField(source='nome_servicos', read_only=True)
    duracao_total = serializers.IntegerField(read_only=True)

    class Meta:
        model = Agendamento
        fields = [
            'id', 'cliente_nome', 'cliente_telefone',
            'servico', 'servico_adicional',
            'servico_nome', 'duracao_total',
            'data', 'hora_inicio', 'hora_fim',
            'status', 'observacoes', 'criado_em',
        ]
        read_only_fields = ['id', 'hora_fim', 'criado_em', 'servico_nome', 'duracao_total']


class AgendamentoCreateSerializer(serializers.ModelSerializer):
    servico_adicional = serializers.PrimaryKeyRelatedField(
        queryset=Servico.objects.filter(ativo=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Agendamento
        fields = [
            'cliente_nome', 'cliente_telefone',
            'servico', 'servico_adicional',
            'data', 'hora_inicio',
            'observacoes',
        ]

    def validate(self, data):
        servico = data['servico']
        servico_adicional = data.get('servico_adicional')
        data_ag = data['data']
        hora_inicio = data['hora_inicio']

        # Duração total
        duracao = servico.duracao_minutos
        if servico_adicional:
            duracao += servico_adicional.duracao_minutos

        # Calcula hora_fim
        inicio_min = minutos(hora_inicio)
        fim_min = inicio_min + duracao

        if fim_min > minutos(HORA_FIM_EXPEDIENTE):
            raise serializers.ValidationError(
                {'hora_inicio': 'O serviço ultrapassa o horário de funcionamento (até 19:00).'}
            )

        data['hora_fim'] = time_from_min(fim_min)

        # Verifica conflito de horários
        conflito = Agendamento.objects.filter(
            data=data_ag,
            hora_inicio__lt=data['hora_fim'],
            hora_fim__gt=hora_inicio,
        ).exclude(status='cancelado')

        if self.instance:
            conflito = conflito.exclude(pk=self.instance.pk)

        if conflito.exists():
            raise serializers.ValidationError(
                {'hora_inicio': 'Este horário já está reservado. Escolha outro horário.'}
            )

        # Verifica se o horário está bloqueado
        from .models import BloqueioHorario
        if BloqueioHorario.objects.filter(data=data_ag, hora=hora_inicio).exists():
            raise serializers.ValidationError(
                {'hora_inicio': 'Este horário está bloqueado pelo estabelecimento.'}
            )

        return data

    def create(self, validated_data):
        return Agendamento.objects.create(**validated_data)