from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# ──────────────────────────────────────────────
# PÁGINAS
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome     = request.form.get("nome")
        cpf      = request.form.get("cpf").replace(".", "").replace("-", "")
        idade    = request.form.get("idade")
        telefone = request.form.get("telefone").replace(" ", "").replace("-", "")
        senha    = request.form.get("senha")

        existing = supabase.table("users").select("id").eq("cpf", cpf).execute()
        if existing.data:
            return render_template("cadastro.html", erro="CPF já cadastrado.")

        supabase.table("users").insert({
            "name": nome,
            "cpf": cpf,
            "age_years": int(idade),
            "phone_number": int(telefone),
            "user_type": "paciente"
        }).execute()

        user = supabase.table("users").select("*").eq("cpf", cpf).single().execute()
        session["user_id"]   = user.data["id"]
        session["user_name"] = user.data["name"]
        session["user_age"]  = user.data["age_years"]

        return redirect(url_for("rotina"))

    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cpf   = request.form.get("cpf").replace(".", "").replace("-", "")
        senha = request.form.get("senha")

        user = supabase.table("users").select("*").eq("cpf", cpf).execute()

        if not user.data:
            return render_template("login.html", erro="CPF não encontrado.")

        session["user_id"]   = user.data[0]["id"]
        session["user_name"] = user.data[0]["name"]
        session["user_age"]  = user.data[0]["age_years"]

        schedule = supabase.table("schedules")\
            .select("*")\
            .eq("user_id", session["user_id"])\
            .execute()

        if schedule.data:
            return redirect(url_for("agendamentos"))
        else:
            return redirect(url_for("rotina"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/rotina")
def rotina():
    if "user_id" not in session:
        return redirect(url_for("login"))

    meds = supabase.table("meds").select("id, name, potency").order("name").execute()
    return render_template("rotina.html", meds=meds.data)


@app.route("/agendamentos")
def agendamentos():
    if "user_id" not in session:
        return redirect(url_for("login"))

    schedule = supabase.table("schedules")\
        .select("*, meds(name, potency)")\
        .eq("user_id", session["user_id"])\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()

    agendamento = schedule.data[0] if schedule.data else None
    return render_template("agendamentos.html", agendamento=agendamento)


# ──────────────────────────────────────────────
# APIs
# ──────────────────────────────────────────────

@app.route("/api/salvar-rotina", methods=["POST"])
def salvar_rotina():
    if "user_id" not in session:
        return jsonify({"erro": "Não autenticado"}), 401

    data = request.get_json()
    meds_id         = data.get("meds_id")
    days_of_intake  = int(data.get("days_of_intake"))
    frequency_hours = int(data.get("frequency_hours"))
    start_datetime  = data.get("start_datetime")  # ISO string

    # Cria o schedule
    schedule = supabase.table("schedules").insert({
        "user_id":         session["user_id"],
        "meds_id":         meds_id,
        "start_datetime":  start_datetime,
        "days_of_intake":  days_of_intake,
        "frequency_hours": frequency_hours
    }).execute()

    schedule_id = schedule.data[0]["id"]

    # Gera as linhas de notifications
    start_dt = datetime.fromisoformat(start_datetime)
    total_doses = (days_of_intake * 24) // frequency_hours
    notifications = []

    for i in range(total_doses):
        notification_dt = start_dt + timedelta(hours=i * frequency_hours)
        notifications.append({
            "schedule_id":           schedule_id,
            "notification_datetime": notification_dt.isoformat(),
            "sent":                  False,
            "cancelled":             False
        })

    supabase.table("notifications").insert(notifications).execute()

    return jsonify({"sucesso": True, "schedule_id": schedule_id})


@app.route("/api/cancelar-rotina", methods=["POST"])
def cancelar_rotina():
    if "user_id" not in session:
        return jsonify({"erro": "Não autenticado"}), 401

    data        = request.get_json()
    schedule_id = data.get("schedule_id")

    # Marca notificações futuras como canceladas
    now = datetime.utcnow().isoformat()
    supabase.table("notifications")\
        .update({"cancelled": True})\
        .eq("schedule_id", schedule_id)\
        .eq("sent", False)\
        .gte("notification_datetime", now)\
        .execute()

    return jsonify({"sucesso": True})


if __name__ == "__main__":
    app.run(debug=True)
