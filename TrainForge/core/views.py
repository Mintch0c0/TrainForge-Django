from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST

import json

from allauth.socialaccount.models import SocialAccount

from .models import (
    Client,
    ClientPreferredTime,
    Plan,
    PlanSession,
    TrainingSessionExercise,
    Appointment,
    ProgressLog,
    TrainerSubscription
)

import calendar
from datetime import date, timedelta, datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# =========================================================
# HELPER FUNCTIONS
# =========================================================


def normalise_time_value(time_value):
    """
    Converts preferred appointment time from form format into a valid Django TimeField value.
    Supports both:
    - 12-hour format: 09:15 AM
    - 24-hour format: 09:15
    """
    if not time_value:
        return None

    time_value = time_value.strip()

    for time_format in ("%I:%M %p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(time_value, time_format).time()
        except ValueError:
            continue

    return None


def format_preferred_time(preferred):
    """
    Prepares preferred appointment time values for display and edit dropdowns.
    This keeps all stored preferred times visible when editing a client.
    """
    time_value = preferred.preferred_time

    return {
        "preferred_day": preferred.preferred_day,
        "preferred_time": time_value,
        "hour": time_value.strftime("%I"),
        "minute": time_value.strftime("%M"),
        "period": time_value.strftime("%p"),
        "form_value": time_value.strftime("%I:%M %p"),
    }


def get_user_initials(user):
    full_name = user.get_full_name()

    if full_name:
        parts = full_name.split()
        return "".join(part[0] for part in parts[:2]).upper()

    if user.email:
        return user.email[:2].upper()

    return user.username[:2].upper()


def get_profile_picture(user):
    social_account = SocialAccount.objects.filter(user=user).first()

    if social_account:
        data = social_account.extra_data

        if "picture" in data:
            return data["picture"]

        if "avatar_url" in data:
            return data["avatar_url"]

    return None


def base_profile_context(user):
    return {
        "profile_initials": get_user_initials(user),
        "profile_picture": get_profile_picture(user),
    }


def openai_response(prompt, fallback):
    try:
        from openai import OpenAI

        client = OpenAI()

        response = client.responses.create(
            model="gpt-5.2",
            input=prompt,
        )

        return response.output_text

    except Exception:
        return fallback


# =========================================================
# AI HELPERS
# =========================================================

def generate_dashboard_insight(total_clients, active_plans, upcoming_sessions, progress_logs):
    if total_clients == 0:
        return (
            "No client data has been added yet. Start by adding clients, creating plans, "
            "and scheduling appointments so TrainForge can generate useful coaching insights."
        )

    if upcoming_sessions == 0 and active_plans == 0:
        return (
            f"You currently have {total_clients} client(s), but no upcoming sessions or active plans. "
            "Create training plans and schedule appointments to make the dashboard more actionable."
        )

    if upcoming_sessions > 0 and active_plans > 0:
        return (
            f"You have {total_clients} client(s), {active_plans} active plan(s), and "
            f"{upcoming_sessions} upcoming session(s). Your dashboard shows active coaching activity, "
            "so the next step is to keep progress logs updated for stronger performance insights."
        )

    return (
        f"Your dashboard is using saved TrainForge data from clients, plans, appointments, and progress logs. "
        f"There are currently {total_clients} client(s), {active_plans} active plan(s), "
        f"{upcoming_sessions} upcoming session(s), and {progress_logs} progress log(s)."
    )


def generate_plan_ai(goal, level, equipment):
    prompt = f"""
    Create a short AI training plan suggestion.

    Goal: {goal}
    Fitness level: {level}
    Equipment access: {equipment}

    Return:
    Plan title:
    Recommended frequency:
    Focus area:
    Trainer note:
    """

    fallback = (
        "Plan title: General Training Program\n"
        "Recommended frequency: 2–3 days per week\n"
        "Focus area: strength and consistency\n"
        "Trainer note: progress gradually and monitor recovery."
    )

    return openai_response(prompt, fallback)


# =========================================================
# AUTH
# =========================================================

def landing(request):
    return render(request, "landing.html")


def auth_page(request):
    mode = request.GET.get("mode", "login")
    error = None

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        # LOGIN
        if form_type == "login":
            email = request.POST.get("email")
            password = request.POST.get("password")

            try:
                user_obj = User.objects.get(email=email)
                username = user_obj.username
            except User.DoesNotExist:
                username = email

            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user:
                login(request, user)
                return redirect("dashboard")

            error = "Invalid email or password."
            mode = "login"

        # SIGNUP
        elif form_type == "signup":
            full_name = request.POST.get("full_name")
            business_name = request.POST.get("business_name")
            email = request.POST.get("email")
            password = request.POST.get("password")
            plan_tier = request.POST.get("plan_tier")

            if User.objects.filter(email=email).exists():
                error = "An account with this email already exists."
                mode = "signup"

            else:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=full_name,
                )

                TrainerSubscription.objects.create(
                    user=user,
                    business_name=business_name,
                    plan_tier=plan_tier,
                    status="Active",
                )

                login(
                    request,
                    user,
                    backend="django.contrib.auth.backends.ModelBackend"
                )
                return redirect("dashboard")

    return render(request, "auth.html", {
        "mode": mode,
        "error": error,
    })


def logout_view(request):
    logout(request)
    return redirect("landing")


# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard(request):
    import calendar
    from datetime import date

    today = timezone.now().date()

    selected_month = int(request.GET.get("month", today.month))
    selected_year = int(request.GET.get("year", today.year))

    month_start = date(selected_year, selected_month, 1)
    _, last_day = calendar.monthrange(selected_year, selected_month)
    month_end = date(selected_year, selected_month, last_day)

    total_clients = Client.objects.filter(trainer_user=request.user).count()
    active_plans = Plan.objects.filter(trainer_user=request.user).count()

    appointments_this_month = Appointment.objects.filter(
        trainer_user=request.user,
        appointment_date__gte=month_start,
        appointment_date__lte=month_end,
    ).order_by("appointment_date", "appointment_time")

    upcoming_appointments = Appointment.objects.filter(
        trainer_user=request.user,
        appointment_date__gte=today,
    ).order_by("appointment_date", "appointment_time")[:4]

    week_counts = [0, 0, 0, 0]

    for appointment in appointments_this_month:
        day = appointment.appointment_date.day

        if day <= 7:
            week_counts[0] += 1
        elif day <= 14:
            week_counts[1] += 1
        elif day <= 21:
            week_counts[2] += 1
        else:
            week_counts[3] += 1

    max_count = max(week_counts) if max(week_counts) > 0 else 1

    chart_points = []
    for index, count in enumerate(week_counts):
        x = 60 + (index * 170)
        completed_y = 220 - ((count / max_count) * 170)
        frequency_y = completed_y

        chart_points.append({
            "label": f"W{index + 1}",
            "completed": count,
            "frequency": count,
            "x": x,
            "completed_y": round(completed_y, 2),
            "frequency_y": round(frequency_y, 2),
            "bar_height": round((count / max_count) * 170, 2),
            "bar_y": round(220 - ((count / max_count) * 170), 2),
        })

    month_options = [
        {"number": i, "name": date(selected_year, i, 1).strftime("%B")}
        for i in range(1, 13)
    ]

    progress_logs = ProgressLog.objects.filter(client__trainer_user=request.user).count()

    context = {
        "total_clients": total_clients,
        "upcoming_sessions": upcoming_appointments.count(),
        "active_plans": active_plans,
        "session_frequency": sum(week_counts),
        "upcoming_appointments": upcoming_appointments,
        "recent_clients": Client.objects.filter(trainer_user=request.user).order_by("-id")[:2],
        "recent_plans": Plan.objects.filter(trainer_user=request.user).order_by("-id")[:2],
        "recent_appointments": appointments_this_month[:2],
        "chart_points": chart_points,
        "selected_month": selected_month,
        "selected_year": selected_year,
        "month_options": month_options,
        "ai_insight": generate_dashboard_insight(
            total_clients,
            active_plans,
            upcoming_appointments.count(),
            progress_logs
        ),
    }

    context.update(base_profile_context(request.user))
    return render(request, "dashboard.html", context)

# =========================================================
# CLIENTS
# =========================================================
def generate_client_ai(goal, status, preferred_day, preferred_time):
    goal_text = goal.lower()

    if "weight" in goal_text:
        focus = "fat loss and cardio progression"
    elif "muscle" in goal_text:
        focus = "strength and hypertrophy"
    elif "fitness" in goal_text:
        focus = "general conditioning"
    else:
        focus = "balanced fitness improvement"

    return (
        f"This client is currently marked as {status.lower()}. "
        f"Recommended coaching focus: {focus}. "
        f"Preferred schedule is {preferred_day} at {preferred_time}. "
        f"Maintain progressive overload while monitoring consistency and recovery."
    )



@login_required
@require_POST
def generate_client_plan_and_note(request):
    """Generate an editable plan title and useful coaching note for the add-client form."""
    name = request.POST.get("name", "this client").strip() or "this client"
    goal = request.POST.get("goal", "General Fitness").strip() or "General Fitness"
    status = request.POST.get("status", "New").strip() or "New"
    current_plan = request.POST.get("plan", "").strip()

    goal_plan_map = {
        "Weight Loss": "Weight Loss Training Program",
        "Muscle Gain": "Muscle Gain Training Program",
        "General Fitness": "General Fitness Training Program",
        "Strength Training": "Strength Training Program",
        "Endurance": "Endurance Training Program",
        "Posture & Mobility": "Posture and Mobility Program",
    }

    fallback_plan = goal_plan_map.get(goal, f"{goal} Training Program")
    fallback_note = (
        f"Program focus: build a realistic routine around {goal.lower()} with clear weekly structure. "
        "Start with manageable intensity, track consistency and recovery, and adjust the program once the client shows stable progress."
    )

    prompt = f"""
    You are helping a personal trainer create client program details.

    Client name: {name}
    Selected goal: {goal}
    Selected status: {status}
    Current plan field typed by trainer: {current_plan or "None"}

    Generate two editable fields:
    1. plan: a short training program title that clearly matches the selected goal.
       If the existing typed plan conflicts with the selected goal, replace it with a better goal-matched plan.
    2. note: an insightful coaching/program note. Do not just repeat the client's status or preferred time.
       Focus on program strategy, training focus, progression, recovery, risk/consideration, and how the trainer should approach the first few weeks.

    Keep the note around 2–3 sentences. Use a practical trainer tone. Do not use markdown.

    Return only valid JSON using this exact structure:
    {{
        "plan": "short plan title",
        "note": "insightful editable trainer note"
    }}
    """

    raw_response = openai_response(
        prompt,
        json.dumps({
            "plan": fallback_plan,
            "note": fallback_note,
        })
    )

    try:
        data = json.loads(raw_response)
        plan = data.get("plan", fallback_plan)
        note = data.get("note", fallback_note)
    except Exception:
        plan = fallback_plan
        note = raw_response if raw_response else fallback_note

    return JsonResponse({
        "plan": plan,
        "note": note,
    })

@login_required
def clients(request):
    search = request.GET.get("search", "")
    status = request.GET.get("status", "All Status")
    goal = request.GET.get("goal", "All Goals")

    clients_list = Client.objects.filter(
        trainer_user=request.user
    ).order_by("-id")

    if search:
        clients_list = clients_list.filter(name__icontains=search)

    if status != "All Status":
        clients_list = clients_list.filter(status=status)

    if goal != "All Goals":
        clients_list = clients_list.filter(goal=goal)

    client_ai = {}

    for client in clients_list:
        preferred_times = list(client.clientpreferredtime_set.all())
        client.preferred_times_data = [
            format_preferred_time(preferred)
            for preferred in preferred_times
        ]

        preferred = preferred_times[0] if preferred_times else None

        client_ai[client.id] = generate_client_ai(
            client.goal,
            client.status,
            preferred.preferred_day if preferred else "",
            preferred.preferred_time if preferred else "",
        )

    context = {
        "clients": clients_list,
        "search": search,
        "status": status,
        "goal": goal,
        "client_ai": client_ai,
    }

    context.update(base_profile_context(request.user))

    return render(request, "clients.html", context)


@login_required
def add_client(request):
    if request.method == "POST":
        client = Client.objects.create(
            trainer_user=request.user,
            name=request.POST.get("name"),
            email=request.POST.get("email"),
            phone=request.POST.get("phone"),
            goal=request.POST.get("goal"),
            status=request.POST.get("status"),
            notes=request.POST.get("notes"),
        )

        # Client creation should not automatically create a training plan.
        # Plans are created from the Training Plans page so empty placeholder
        # plans do not appear as "Has Plan".
        preferred_days = request.POST.getlist("preferred_day")
        preferred_times = request.POST.getlist("preferred_time")

        for preferred_day, preferred_time in zip(preferred_days, preferred_times):
            converted_time = normalise_time_value(preferred_time)

            if preferred_day and converted_time:
                ClientPreferredTime.objects.create(
                    client=client,
                    preferred_day=preferred_day,
                    preferred_time=converted_time,
                )

    return redirect("clients")


@login_required
def edit_client(request, client_id):
    client = get_object_or_404(
        Client,
        id=client_id,
        trainer_user=request.user
    )

    if request.method == "POST":
        client.name = request.POST.get("name")
        client.email = request.POST.get("email")
        client.phone = request.POST.get("phone")
        client.goal = request.POST.get("goal")
        client.status = request.POST.get("status")
        client.notes = request.POST.get("notes")
        client.save()

        client.clientpreferredtime_set.all().delete()

        preferred_days = request.POST.getlist("preferred_day")
        preferred_times = request.POST.getlist("preferred_time")

        for preferred_day, preferred_time in zip(preferred_days, preferred_times):
            converted_time = normalise_time_value(preferred_time)

            if preferred_day and converted_time:
                ClientPreferredTime.objects.create(
                    client=client,
                    preferred_day=preferred_day,
                    preferred_time=converted_time,
                )

    return redirect("clients")


@login_required
def delete_client(request, client_id):
    client = get_object_or_404(
        Client,
        id=client_id,
        trainer_user=request.user
    )

    if request.method == "POST":
        client.delete()

    return redirect("clients")


# =========================================================
# PLANS
# =========================================================

@login_required
def plans(request):
    search = request.GET.get("search", "")

    clients = Client.objects.filter(
        trainer_user=request.user
    ).order_by("-id")

    if search:
        clients = clients.filter(name__icontains=search)

    plan_rows = []

    for client in clients:
        # Only show a client as having a plan when the plan has saved day/session content.
        # This prevents AI-created client notes from appearing as empty plans.
        plan = (
            Plan.objects
            .filter(
                client=client,
                trainer_user=request.user,
                plansession__isnull=False,
            )
            .distinct()
            .first()
        )

        plan_rows.append({
            "client": client,
            "plan": plan,
            "preferred_times": ClientPreferredTime.objects.filter(
                client=client
            )
        })

    context = {
        "plan_rows": plan_rows,
        "search": search,
    }

    context.update(base_profile_context(request.user))

    return render(request, "plans.html", context)


@login_required
def create_plan(request, client_id):
    client = get_object_or_404(
        Client,
        id=client_id,
        trainer_user=request.user
    )

    if request.method == "POST":
        # Remove empty placeholder plans before saving a real plan for this client.
        Plan.objects.filter(
            client=client,
            trainer_user=request.user,
            plansession__isnull=True,
        ).delete()

        plan = Plan.objects.create(
            client=client,
            trainer_user=request.user,
            plan_title=request.POST.get("plan_title"),
            goal_type=request.POST.get("goal_type"),
            fitness_level=request.POST.get("fitness_level"),
            training_frequency=request.POST.get("training_frequency"),
            equipment_access=request.POST.get("equipment_access"),
            limitations_trainer_notes=request.POST.get("notes"),
        )

        session_titles = request.POST.getlist("session_day_label")
        exercise_names = request.POST.getlist("exercise_name")
        descriptions = request.POST.getlist("exercise_description")
        sets_counts = request.POST.getlist("sets_count")
        reps_counts = request.POST.getlist("reps_count")
        rest_seconds = request.POST.getlist("rest_seconds")
        exercise_notes = request.POST.getlist("exercise_notes")

        for index, session_title in enumerate(session_titles):
            if not session_title:
                continue

            session = PlanSession.objects.create(
                plan=plan,
                session_day_label=session_title,
                display_order=index + 1,
            )

            exercise_name = exercise_names[index] if index < len(exercise_names) else ""

            if exercise_name:
                TrainingSessionExercise.objects.create(
                    plan_session=session,
                    exercise_name=exercise_name,
                    description=descriptions[index] if index < len(descriptions) else "",
                    sets_count=sets_counts[index] if index < len(sets_counts) and sets_counts[index] else 0,
                    reps_count=reps_counts[index] if index < len(reps_counts) and reps_counts[index] else 0,
                    rest_seconds=rest_seconds[index] if index < len(rest_seconds) and rest_seconds[index] else 0,
                    trainer_notes=exercise_notes[index] if index < len(exercise_notes) else "",
                )

    return redirect("plans")



@login_required
def update_plan(request, plan_id):
    plan = get_object_or_404(
        Plan,
        id=plan_id,
        trainer_user=request.user
    )

    if request.method == "POST":
        plan.plan_title = request.POST.get("plan_title")
        plan.goal_type = request.POST.get("goal_type")
        plan.fitness_level = request.POST.get("fitness_level")
        plan.training_frequency = request.POST.get("training_frequency")
        plan.equipment_access = request.POST.get("equipment_access")
        plan.limitations_trainer_notes = request.POST.get("notes")
        plan.save()

        # Rebuild the simple training-day structure from the submitted form.
        # This keeps the dynamic "+ Add Training Day" button aligned with saved data.
        plan.plansession_set.all().delete()

        session_titles = request.POST.getlist("session_day_label")
        exercise_names = request.POST.getlist("exercise_name")
        descriptions = request.POST.getlist("exercise_description")
        sets_counts = request.POST.getlist("sets_count")
        reps_counts = request.POST.getlist("reps_count")
        rest_seconds = request.POST.getlist("rest_seconds")
        exercise_notes = request.POST.getlist("exercise_notes")

        for index, session_title in enumerate(session_titles):
            if not session_title:
                continue

            session = PlanSession.objects.create(
                plan=plan,
                session_day_label=session_title,
                display_order=index + 1,
            )

            exercise_name = exercise_names[index] if index < len(exercise_names) else ""

            if exercise_name:
                TrainingSessionExercise.objects.create(
                    plan_session=session,
                    exercise_name=exercise_name,
                    description=descriptions[index] if index < len(descriptions) else "",
                    sets_count=sets_counts[index] if index < len(sets_counts) and sets_counts[index] else 0,
                    reps_count=reps_counts[index] if index < len(reps_counts) and reps_counts[index] else 0,
                    rest_seconds=rest_seconds[index] if index < len(rest_seconds) and rest_seconds[index] else 0,
                    trainer_notes=exercise_notes[index] if index < len(exercise_notes) else "",
                )

    return redirect("plans")



@login_required
def delete_plan(request, plan_id):
    plan = get_object_or_404(
        Plan,
        id=plan_id,
        trainer_user=request.user
    )

    if request.method == "POST":
        plan.delete()

    return redirect("plans")


# =========================================================
# PROFILE
# =========================================================

@login_required
def profile(request):
    context = base_profile_context(request.user)
    return render(request, "profile.html", context)


# =========================================================
# APPOINTMENTS
# =========================================================

@login_required
def appointments(request):
    today = timezone.now().date()

    appointments_list = Appointment.objects.filter(
        trainer_user=request.user
    ).order_by("appointment_date", "appointment_time")

    month_start = today.replace(day=1)
    _, days_in_month = calendar.monthrange(today.year, today.month)
    month_end = today.replace(day=days_in_month)

    start_calendar = month_start - timedelta(days=month_start.weekday())
    end_calendar = month_end + timedelta(days=(6 - month_end.weekday()))

    calendar_days = []
    current_day = start_calendar

    while current_day <= end_calendar:
        day_appointments = appointments_list.filter(
            appointment_date=current_day
        )

        calendar_days.append({
            "date": current_day,
            "in_month": current_day.month == today.month,
            "appointments": day_appointments,
        })

        current_day += timedelta(days=1)

    context = {
        "clients": Client.objects.filter(
            trainer_user=request.user
        ).order_by("name"),
        "appointments": appointments_list,
        "upcoming_appointments": appointments_list.filter(
            appointment_date__gte=today
        )[:5],
        "calendar_days": calendar_days,
        "current_month_name": today.strftime("%B"),
        "current_year": today.year,
    }

    context.update(base_profile_context(request.user))

    return render(request, "appointments.html", context)


@login_required
def add_appointment(request):
    if request.method == "POST":
        client = get_object_or_404(
            Client,
            id=request.POST.get("client_id"),
            trainer_user=request.user
        )

        Appointment.objects.create(
            client=client,
            trainer_user=request.user,
            session_type=request.POST.get("session_type"),
            appointment_date=request.POST.get("appointment_date"),
            appointment_time=request.POST.get("appointment_time"),
            note=request.POST.get("note"),
        )

    return redirect("appointments")


@login_required
def delete_appointment(request, appointment_id):
    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        trainer_user=request.user
    )

    if request.method == "POST":
        appointment.delete()

    return redirect("appointments")

@login_required
def progress(request):
    clients = Client.objects.filter(
        trainer_user=request.user
    ).order_by("name")

    selected_client_id = request.GET.get("client")
    selected_exercise = request.GET.get("exercise", "")

    selected_client = None
    progress_logs = ProgressLog.objects.none()
    exercise_options = []

    if clients.exists():
        selected_client = clients.filter(id=selected_client_id).first() if selected_client_id else clients.first()

        progress_logs = ProgressLog.objects.filter(
            client=selected_client
        ).order_by("id")

        exercise_options = list(
            ProgressLog.objects.filter(client=selected_client)
            .values_list("exercise_name", flat=True)
            .distinct()
        )

        if not selected_exercise and exercise_options:
            selected_exercise = exercise_options[0]

        if selected_exercise:
            progress_logs = progress_logs.filter(exercise_name=selected_exercise)

    latest_log = progress_logs.last()
    first_log = progress_logs.first()

    weight_change = 0
    reps_change = 0

    if latest_log and first_log:
        weight_change = float(latest_log.weight or 0) - float(first_log.weight or 0)
        reps_change = int(latest_log.reps or 0) - int(first_log.reps or 0)

    if latest_log:
        if weight_change > 0 or reps_change > 0:
            trend = "Improving"
            recommendation = "The client is progressing well. Consider a small increase in load, reps, or exercise difficulty while keeping technique consistent."
        elif weight_change <= 0 and reps_change <= 0:
            trend = "Plateau"
            recommendation = "Progress appears to be slowing. Review recovery, consistency, and exercise variation before increasing intensity."
        else:
            trend = "Stable"
            recommendation = "Maintain the current program and continue monitoring performance."
    else:
        trend = "No insight yet"
        recommendation = "Add progress logs to generate a clearer coaching insight."

    chart_points = []
    logs_list = list(progress_logs)
    total_logs = len(logs_list)

    for index, log in enumerate(logs_list):

        x_position = 40

        if total_logs > 1:
            x_position = 40 + (index * (540 / (total_logs - 1)))

        chart_points.append({
            "label": log.log_label,
            "weight": float(log.weight or 0),
            "reps": int(log.reps or 0),
            "svg_x": round(x_position, 2),
        })

    max_weight = max([point["weight"] for point in chart_points], default=1)
    max_reps = max([point["reps"] for point in chart_points], default=1)

    for point in chart_points:

        point["weight_svg_y"] = round(
            220 - ((point["weight"] / max_weight) * 180),
            2
        )

        point["reps_svg_y"] = round(
            220 - ((point["reps"] / max_reps) * 180),
            2
        )

        point["tooltip_x"] = max(45, min(point["svg_x"] + 8, 500))
        point["tooltip_y"] = max(25, point["weight_svg_y"] - 55)
        point["tooltip_text_x"] = point["tooltip_x"] + 10
        point["tooltip_text_y_1"] = point["tooltip_y"] + 18
        point["tooltip_text_y_2"] = point["tooltip_y"] + 36

    for point in chart_points:
        point["reps_bar_height"] = round(
            (point["reps"] / max_reps) * 100,
            2
        )

    context = {
        "clients": clients,
        "selected_client": selected_client,
        "selected_exercise": selected_exercise,
        "exercise_options": exercise_options,
        "progress_logs": progress_logs,
        "latest_log": latest_log,
        "weight_change": weight_change,
        "reps_change": reps_change,
        "trend": trend,
        "recommendation": recommendation,
        "chart_points": chart_points,
        "max_weight": max_weight,
        "max_reps": max_reps,
        "client_plans": Plan.objects.filter(trainer_user=request.user),
    }

    context.update(base_profile_context(request.user))

    return render(request, "progress.html", context)


@login_required
def add_progress_log(request):
    if request.method == "POST":
        client = get_object_or_404(
            Client,
            id=request.POST.get("client_id"),
            trainer_user=request.user
        )

        plan = Plan.objects.filter(
            client=client,
            trainer_user=request.user
        ).first()

        if not plan:
            plan = Plan.objects.create(
                client=client,
                trainer_user=request.user,
                plan_title=f"{client.name} Progress Plan",
                goal_type=client.goal or "General Fitness",
                fitness_level="Beginner",
                training_frequency="2 Days / Week",
                equipment_access="Full Gym",
                limitations_trainer_notes="Auto-created plan for progress tracking."
            )

        ProgressLog.objects.create(
            client=client,
            plan=plan,
            exercise_name=request.POST.get("exercise_name"),
            log_label=request.POST.get("log_label"),
            weight=request.POST.get("weight") or 0,
            reps=request.POST.get("reps") or 0,
        )

    return redirect("progress")

@login_required
def edit_progress_log(request, log_id):
    log = get_object_or_404(
        ProgressLog,
        id=log_id,
        client__trainer_user=request.user
    )

    if request.method == "POST":
        log.exercise_name = request.POST.get("exercise_name")
        log.log_label = request.POST.get("log_label")
        log.weight = request.POST.get("weight") or 0
        log.reps = request.POST.get("reps") or 0
        log.save()

    return redirect("progress")


@login_required
def delete_progress_log(request, log_id):
    log = get_object_or_404(
        ProgressLog,
        id=log_id,
        client__trainer_user=request.user
    )

    if request.method == "POST":
        log.delete()

    return redirect("progress")

@login_required
def subscriptions(request):
    search = request.GET.get("search", "")
    status = request.GET.get("status", "All Status")
    plan = request.GET.get("plan", "All Plans")

    subscriptions_list = TrainerSubscription.objects.select_related("user").order_by("-id")

    if search:
        subscriptions_list = subscriptions_list.filter(
            user__first_name__icontains=search
        ) | subscriptions_list.filter(
            user__email__icontains=search
        ) | subscriptions_list.filter(
            business_name__icontains=search
        )

    if status != "All Status":
        subscriptions_list = subscriptions_list.filter(status=status)

    if plan != "All Plans":
        subscriptions_list = subscriptions_list.filter(plan_tier=plan)

    paginator = Paginator(subscriptions_list, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "subscriptions": page_obj,
        "page_obj": page_obj,
        "search": search,
        "status": status,
        "plan": plan,
        "total_results": subscriptions_list.count(),
    }

    context.update(base_profile_context(request.user))

    return render(request, "subscriptions.html", context)


@login_required
def add_subscription(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        business_name = request.POST.get("business_name")
        plan_tier = request.POST.get("plan_tier")
        status = request.POST.get("status")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": full_name,
            }
        )

        user.first_name = full_name
        user.username = email

        if password:
            user.set_password(password)

        user.save()

        subscription, created = TrainerSubscription.objects.get_or_create(
            user=user,
            defaults={
                "business_name": business_name,
                "plan_tier": plan_tier,
                "status": status,
            }
        )

        if not created:
            subscription.business_name = business_name
            subscription.plan_tier = plan_tier
            subscription.status = status
            subscription.save()

    return redirect("subscriptions")


@login_required
def edit_subscription(request, subscription_id):
    subscription = get_object_or_404(
        TrainerSubscription,
        id=subscription_id
    )

    if request.method == "POST":
        subscription.user.first_name = request.POST.get("full_name")
        subscription.user.email = request.POST.get("email")
        subscription.user.username = request.POST.get("email")

        password = request.POST.get("password")
        if password:
            subscription.user.set_password(password)

        subscription.user.save()

        subscription.business_name = request.POST.get("business_name")
        subscription.plan_tier = request.POST.get("plan_tier")
        subscription.status = request.POST.get("status")
        subscription.save()

    return redirect("subscriptions")


@login_required
def archive_subscription(request, subscription_id):
    subscription = get_object_or_404(
        TrainerSubscription,
        id=subscription_id
    )

    if request.method == "POST":
        subscription.status = "Archived"
        subscription.save()

    return redirect("subscriptions")