from rest_framework import serializers
from datetime import datetime, timedelta, time
from .models import Servico, Agendamento, BloqueioHorario
from .disponibilidade import HORA_FIM_EXPEDIENTE, avaliar_slot


def minutos(t: time) -> int:
    return t.hour * 60 + t.minute


def time_from_min(m: int) -> time:
    return time(m // 60, m % 60)


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

        # Usa a mesma regra de encaixe da consulta pública de horários.
        agendamentos = Agendamento.objects.filter(data=data_ag).exclude(status='cancelado')
        if self.instance:
            agendamentos = agendamentos.exclude(pk=self.instance.pk)
        bloqueios = BloqueioHorario.objects.filter(data=data_ag)
        disponivel, _, motivo = avaliar_slot(
            data_ag, hora_inicio, duracao, list(agendamentos), list(bloqueios)
        )
        if not disponivel:
            if motivo == 'bloqueio':
                mensagem = 'Este horário está bloqueado pelo estabelecimento.'
            elif motivo == 'expediente':
                mensagem = 'O serviço ultrapassa o horário de funcionamento (até 19:00).'
            elif motivo == 'fechado':
                mensagem = 'O estabelecimento não atende aos domingos.'
            else:
                mensagem = 'Este horário já está reservado. Escolha outro horário.'
            raise serializers.ValidationError({'hora_inicio': mensagem})

        return data

    def create(self, validated_data):
        return Agendamento.objects.create(**validated_data)
