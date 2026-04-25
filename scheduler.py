from apscheduler.schedulers.background import BackgroundScheduler
from supabase import create_client, Client
from twilio.rest import Client as TwilioClient
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

twilio = TwilioClient(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")  # ex: whatsapp:+14155238886


def formatar_telefone(numero: int) -> str:
    """Converte número brasileiro para formato E.164 com DDI."""
    tel = str(int(numero))
    if not tel.startswith("55"):
        tel = "55" + tel
    return f"whatsapp:+{tel}"


def disparar_notificacoes():
    agora = datetime.now(timezone.utc).isoformat()

    pendentes = supabase.table("notifications")\
        .select("*, schedules(user_id, meds_id, meds(name, potency), users(name, phone_number))")\
        .eq("sent", False)\
        .eq("cancelled", False)\
        .lte("notification_datetime", agora)\
        .execute()

    for notif in pendentes.data:
        try:
            schedule  = notif["schedules"]
            user      = schedule["users"]
            med       = schedule["meds"]
            telefone  = formatar_telefone(user["phone_number"])
            nome      = user["name"].split()[0]  # Primeiro nome

            mensagem = (
                f"Olá, {nome}! 💊\n"
                f"Está na hora de tomar seu remédio:\n"
                f"*{med['name']} {int(med['potency'])}mg*\n\n"
                f"Dose Certa 🩺"
            )

            twilio.messages.create(
                body=mensagem,
                from_=TWILIO_WHATSAPP_FROM,
                to=telefone
            )

            supabase.table("notifications")\
                .update({"sent": True})\
                .eq("id", notif["id"])\
                .execute()

            print(f"[OK] Notificação enviada para {nome} ({telefone})")

        except Exception as e:
            print(f"[ERRO] Notificação {notif['id']}: {e}")


def iniciar_scheduler():
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(disparar_notificacoes, "interval", minutes=30)
    scheduler.start()
    print("[Scheduler] Rodando — verificando notificações a cada 30 minutos.")
    return scheduler
