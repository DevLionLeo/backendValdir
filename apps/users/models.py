from django.db import models


class Servico(models.Model):
    CATEGORIA_CHOICES = [
        ('masculino', 'Masculino'),
        ('feminino', 'Feminino'),
    ]

    nome = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='masculino')
    duracao_minutos = models.IntegerField()
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Serviço'
        verbose_name_plural = 'Serviços'
        ordering = ['categoria', 'nome']

    def __str__(self):
        return f'{self.get_categoria_display()} — {self.nome} ({self.duracao_minutos} min)'


class BloqueioHorario(models.Model):
    """Horários bloqueados pelo administrador."""
    data = models.DateField(verbose_name='Data')
    hora = models.TimeField(verbose_name='Horário bloqueado')
    motivo = models.CharField(max_length=200, blank=True, verbose_name='Motivo')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bloqueio de Horário'
        verbose_name_plural = 'Bloqueios de Horários'
        ordering = ['data', 'hora']
        unique_together = ['data', 'hora']

    def __str__(self):
        return f'Bloqueio: {self.data} às {self.hora}'


class Agendamento(models.Model):
    STATUS_CHOICES = [
        ('confirmado', 'Confirmado'),
        ('cancelado', 'Cancelado'),
        ('concluido', 'Concluído'),
    ]

    cliente_nome = models.CharField(max_length=150, verbose_name='Nome do cliente')
    cliente_telefone = models.CharField(max_length=20, verbose_name='Telefone')

    # Serviço principal
    servico = models.ForeignKey(
        Servico, on_delete=models.PROTECT,
        related_name='agendamentos_principal',
        verbose_name='Serviço principal'
    )
    # Serviço adicional (opcional — executado logo após o principal)
    servico_adicional = models.ForeignKey(
        Servico, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='agendamentos_adicional',
        verbose_name='Serviço adicional'
    )

    data = models.DateField(verbose_name='Data')
    hora_inicio = models.TimeField(verbose_name='Hora de início')
    hora_fim = models.TimeField(verbose_name='Hora de fim')  # calculado automaticamente

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmado')
    observacoes = models.TextField(blank=True, verbose_name='Observações')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Agendamento'
        verbose_name_plural = 'Agendamentos'
        ordering = ['data', 'hora_inicio']

    def duracao_total(self):
        total = self.servico.duracao_minutos
        if self.servico_adicional:
            total += self.servico_adicional.duracao_minutos
        return total

    def nome_servicos(self):
        if self.servico_adicional:
            return f'{self.servico.nome} + {self.servico_adicional.nome}'
        return self.servico.nome

    def __str__(self):
        return f'{self.cliente_nome} — {self.nome_servicos()} em {self.data} às {self.hora_inicio}'