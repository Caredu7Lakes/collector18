"""Parser do contactMessage da Evolution (payload.data.message.contactMessage).

O card traz displayName + uma string vCard. Extraímos nome, telefones, nome
comercial (ORG) e descrição (NOTE), como no exemplo do alfaiate 'Villa Alta Costura'.
"""

import re

_TEL = re.compile(r"^TEL[^:]*:(.+)$", re.IGNORECASE | re.MULTILINE)
_FN = re.compile(r"^FN[^:]*:(.+)$", re.IGNORECASE | re.MULTILINE)
_ORG = re.compile(r"^ORG[^:]*:(.+)$", re.IGNORECASE | re.MULTILINE)
_NOTE = re.compile(r"^NOTE[^:]*:(.+)$", re.IGNORECASE | re.MULTILINE)
_DIGITS = re.compile(r"\D+")


def _clean_phone(raw: str) -> str:
    # mantém dígitos; preserva '+' inicial se houver
    plus = raw.strip().startswith("+")
    d = _DIGITS.sub("", raw)
    return ("+" + d) if plus and d else d


def parse_contact(contact_message: dict, fallback_name: str | None = None) -> dict:
    vcard = contact_message.get("vcard", "") or ""
    display = contact_message.get("displayName") or fallback_name

    fn = _FN.search(vcard)
    name = (fn.group(1).strip() if fn else None) or display or "Sem nome"

    phones = [_clean_phone(m.group(1)) for m in _TEL.finditer(vcard)]
    phones = [p for p in dict.fromkeys(phones) if p]  # dedup, preserva ordem

    org = _ORG.search(vcard)
    note = _NOTE.search(vcard)

    return {
        "display_name": name,
        "phones": phones,
        "business_name": org.group(1).strip() if org else None,
        "description": note.group(1).strip() if note else None,
    }
