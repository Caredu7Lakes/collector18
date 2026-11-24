"""build_indicacoes_xlsx: cabeçalho na linha 1, dados da 2, telefones unidos por ';'."""

import io
from types import SimpleNamespace

from openpyxl import load_workbook

from app.export_builder import build_indicacoes_xlsx


def test_shape_indicacoes_e_contatos():
    inds = [SimpleNamespace(provider_name="Alfaiate João", servico_termo="alfaiate", phone="5511999998888")]
    contacts = [
        SimpleNamespace(
            display_name="Marcenaria Silva",
            business_name="Marcenaria",
            phones=["5511888887777", "1140001000"],
        )
    ]
    data = build_indicacoes_xlsx(inds, contacts)

    ws = load_workbook(io.BytesIO(data)).active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("Contato", "Serviço", "Telefone")
    assert rows[1] == ("Alfaiate João", "alfaiate", "5511999998888")
    assert rows[2] == ("Marcenaria Silva", "Marcenaria", "5511888887777;1140001000")
