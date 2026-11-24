"""Expurgo de retenção: a janela de corte é received_at - retention_days."""

from datetime import UTC, datetime

from scripts.purge_raw import cutoff


def test_cutoff_subtrai_janela_de_retencao():
    now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=UTC)
    assert (now - cutoff(now, 90)).days == 90


def test_cutoff_zero_nao_expurga_futuro():
    now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=UTC)
    assert cutoff(now, 0) == now