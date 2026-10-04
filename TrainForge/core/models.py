from django.db import models
from django.contrib.auth.models import User

# Subscription models
class TrainerSubscription(models.Model):
    """Stores SaaS subscription information for trainer accounts."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=100, blank=True)
    plan_tier = models.CharField(max_length=20, default="Starter")
    status = models.CharField(max_length=20, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.plan_tier}"

# Client models
class Client(models.Model):
    """Stores client profile information linked to a trainer."""
    trainer_user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    goal = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=30, default="Active")
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ClientPreferredTime(models.Model):
    """Stores one or more preferred appointment times for a client."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    preferred_day = models.CharField(max_length=20)
    preferred_time = models.TimeField()

    def __str__(self):
        return f"{self.client.name} - {self.preferred_day}"

# Training Plan models
class Plan(models.Model):
    """Stores the high-level training plan details for a client."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    trainer_user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan_title = models.CharField(max_length=120)
    goal_type = models.CharField(max_length=100)
    fitness_level = models.CharField(max_length=50, blank=True)
    training_frequency = models.CharField(max_length=50, blank=True)
    equipment_access = models.CharField(max_length=100, blank=True)
    limitations_trainer_notes = models.TextField(blank=True)

    def __str__(self):
        return self.plan_title


class PlanSession(models.Model):
    """Stores individual training days within a plan."""
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    session_day_label = models.CharField(max_length=50)
    display_order = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.plan.plan_title} - {self.session_day_label}"


class TrainingSessionExercise(models.Model):
    """Stores exercises assigned to a specific training day."""
    plan_session = models.ForeignKey(PlanSession, on_delete=models.CASCADE)
    exercise_name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    sets_count = models.IntegerField(default=0)
    reps_count = models.IntegerField(default=0)
    rest_seconds = models.IntegerField(default=0)
    trainer_notes = models.TextField(blank=True)

    def __str__(self):
        return self.exercise_name

# Appointment models
class Appointment(models.Model):
    """Stores scheduled client appointments."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    trainer_user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_type = models.CharField(max_length=50)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.client.name} - {self.appointment_date}"

# Progress models
class ProgressLog(models.Model):
    """Stores logged performance data for a client's exercise progress."""
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    exercise_name = models.CharField(max_length=120)
    log_label = models.CharField(max_length=50)
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    reps = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.client.name} - {self.exercise_name}"
    