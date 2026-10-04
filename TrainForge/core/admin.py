from django.contrib import admin

from .models import (
    TrainerSubscription,
    Client,
    ClientPreferredTime,
    Plan,
    PlanSession,
    TrainingSessionExercise,
    Appointment,
    ProgressLog,
)

admin.site.register(TrainerSubscription)
admin.site.register(Client)
admin.site.register(ClientPreferredTime)
admin.site.register(Plan)
admin.site.register(PlanSession)
admin.site.register(TrainingSessionExercise)
admin.site.register(Appointment)
admin.site.register(ProgressLog)