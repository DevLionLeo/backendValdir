"""Regra única de disponibilidade para consulta e criação de agendamentos."""

from datetime import time


HORA_INICIO_EXPEDIENTE = time(8, 0)
HORA_FIM_EXPEDIENTE = time(19, 0)
INTERVALO_MINUTOS = 30


def minutos(horario: time) -> int:
    return horario.hour * 60 + horario.minute


def avaliar_slot(data, hora_inicio, duracao, agendamentos, bloqueios):
    """Retorna (disponivel, encaixe, motivo).

    Um encaixe só pode durar 30 minutos e estar inteiramente dentro de um
    único agendamento ativo com duração de pelo menos três horas. Outros
    agendamentos e bloqueios continuam impedindo o uso desse intervalo.
    """
    inicio = minutos(hora_inicio)
    fim = inicio + duracao

    if data.weekday() == 6:
        return False, False, "fechado"
    if duracao <= 0 or inicio < minutos(HORA_INICIO_EXPEDIENTE) or fim > minutos(HORA_FIM_EXPEDIENTE):
        return False, False, "expediente"

    # Cada bloqueio representa um intervalo de 30 minutos.
    if any(inicio < minutos(b.hora) + INTERVALO_MINUTOS and fim > minutos(b.hora) for b in bloqueios):
        return False, False, "bloqueio"

    conflitos = [
        ag for ag in agendamentos
        if ag.status != "cancelado"
        and inicio < minutos(ag.hora_fim)
        and fim > minutos(ag.hora_inicio)
    ]
    if not conflitos:
        return True, False, None

    if duracao == INTERVALO_MINUTOS and len(conflitos) == 1:
        longo = conflitos[0]
        longo_inicio = minutos(longo.hora_inicio)
        longo_fim = minutos(longo.hora_fim)
        if longo_fim - longo_inicio >= 180 and longo_inicio <= inicio and fim <= longo_fim:
            return True, True, None

    return False, False, "conflito"
