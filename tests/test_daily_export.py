"""day_start normaliza p/ meia-noite Brasília; o MIME do SES carrega o XLSX anexado."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.ses_mailer import build_message
from scripts.daily_export import TZ, day_start


def test_day_start_meia_noite_brasilia():
    now = datetime(2026, 11, 24, 23, 54, tzinfo=TZ)
    s = day_start(now)
    assert (s.hour, s.minute, s.second) == (0, 0, 0)
    assert s.date() == now.date()


def test_day_start_usa_o_dia_local_nao_utc():
    now = datetime(2026, 11, 25, 2, 54, tzinfo=ZoneInfo("UTC"))
    assert day_start(now).day == 24


def test_mime_carrega_o_xlsx_anexado():
    raw = build_message(
        sender="de@x.com",
        recipient="para@x.com",
        subject="assunto",
        body="corpo",
        xlsx=b"PK\x03\x04conteudo-fake",
        filename="indicacoes_20261124.xlsx",
    )
    assert "para@x.com" in raw
    assert "indicacoes_20261124.xlsx" in raw
    assert "attachment" in raw
    assert "spreadsheetml.sheet" in raw
