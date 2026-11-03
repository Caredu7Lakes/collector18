from app.services.vcard import parse_contact

# Espelha o card do exemplo: Alfaiate DEDÉ / Villa Alta Costura, 2 telefones.
VCARD = (
    "BEGIN:VCARD\n"
    "VERSION:3.0\n"
    "FN:Alfaiate DEDÉ ajuste De Roupa Masculino\n"
    "ORG:Villa Alta Costura\n"
    "TEL;type=CELL:+55 19 99730-5727\n"
    "TEL;type=HOME:+55 19 3325-3107\n"
    "NOTE:ateliê de costura, ternos, camisas, calças\n"
    "END:VCARD"
)


def test_parse_contact_full():
    out = parse_contact({"displayName": "Alfaiate DEDÉ", "vcard": VCARD})
    assert out["business_name"] == "Villa Alta Costura"
    assert out["phones"] == ["+5519997305727", "+551933253107"]
    assert "ateliê" in out["description"]
    assert out["display_name"].startswith("Alfaiate DEDÉ")


def test_parse_contact_fallback_name():
    out = parse_contact({"vcard": "BEGIN:VCARD\nTEL:11999999999\nEND:VCARD"}, fallback_name="Zé")
    assert out["display_name"] == "Zé"
    assert out["phones"] == ["11999999999"]
    assert out["business_name"] is None
