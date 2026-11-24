"""Envio de e-mail com anexo via Amazon SES (SendRawEmail).

Autentica pelo instance profile da EC2 (boto3 pega as credenciais via IMDS) — sem
segredo estático no .env. SendRawEmail é o que suporta anexo (o SES simples e o SNS
não carregam arquivo). Remetente/destinatário vêm do ambiente.
"""

import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.export_builder import XLSX_MEDIA_TYPE


def build_message(sender: str, recipient: str, subject: str, body: str, xlsx: bytes, filename: str) -> str:
    """Monta a mensagem MIME (multipart) com corpo + anexo XLSX. Retorna a string pronta."""
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body, "plain", "utf-8"))

    part = MIMEApplication(xlsx, _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    part.add_header("Content-Disposition", "attachment", filename=filename)
    part.replace_header("Content-Type", f'{XLSX_MEDIA_TYPE}; name="{filename}"')
    msg.attach(part)
    return msg.as_string()


def send_xlsx(subject: str, body: str, xlsx: bytes, filename: str) -> str:
    """Envia o XLSX por SES. Retorna o MessageId. Lê EXPORT_EMAIL_FROM/TO e AWS_REGION."""
    import boto3

    sender = os.environ["EXPORT_EMAIL_FROM"]
    recipient = os.environ["EXPORT_EMAIL_TO"]
    region = os.environ.get("AWS_REGION", "us-west-2")

    raw = build_message(sender, recipient, subject, body, xlsx, filename)
    ses = boto3.client("ses", region_name=region)
    resp = ses.send_raw_email(Source=sender, Destinations=[recipient], RawMessage={"Data": raw})
    return resp["MessageId"]
