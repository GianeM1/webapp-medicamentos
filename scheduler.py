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

TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")


def formatar_telefone(numero) -> str:
    """Converte número brasileiro para formato E.164 com DDI."""
    tel = str(int(numero))
    if not tel.startswith("55"):
        tel = "55" + tel
    return f"whatsapp:+{tel}"


def disparar_notificacoes():
    agora = datetime.now(timezone.utc).isoformat()
    print(f"[Scheduler] Verificando notificações pendentes em {agora}")

    pendentes = supabase.table("notifications")\
        .select("id, schedule_id")\
        .eq("sent", False)\
        .eq("cancelled", False)\
        .lte("notification_datetime", agora)\
        .execute()

    print(f"[Scheduler] {len(pendentes.data)} notificação(ões) encontrada(s)")

    for notif in pendentes.data:
        try:
            # Busca o schedule
            schedule = supabase.table("schedules")\
                .select("user_id, meds_id")\
                .eq("id", notif["schedule_id"])\
                .single()\
                .execute()

            # Busca o usuário
            user = supabase.table("users")\
                .select("name, phone_number")\
                .eq("id", schedule.data["user_id"])\
                .single()\
                .execute()

            # Busca o medicamento
            med = supabase.table("meds")\
                .select("name, potency")\
                .eq("id", schedule.data["meds_id"])\
                .single()\
                .execute()

            telefone = formatar_telefone(user.data["phone_number"])
            nome     = user.data["name"].split()[0]

            mensagem = (
                f"Olá, {nome}! 💊\n"
                f"Está na hora de tomar seu remédio:\n"
                f"*{med.data['name']} {int(med.data['potency'])}mg*\n\n"
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

            print(f"[OK] Notificação {notif['id']} enviada para {nome} ({telefone})")

        except Exception as e:
            print(f"[ERRO] Notificação {notif['id']}: {e}")


def iniciar_scheduler():
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(disparar_notificacoes, "interval", minutes=5)
    scheduler.start()
    print("[Scheduler] Rodando — verificando notificações a cada 5 minutos.")
    return scheduler
