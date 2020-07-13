"""Constants for the onboarding component."""
DOMAIN = "onboarding"
STEP_USER = "user"
STEP_CORE_CONFIG = "core_config"
STEP_INTEGRATION = "integration"
STEP_MOB_INTEGRATION = "mob_integration"
STEP_AIS_RESTORE_BACKUP = "ais_restore_backup"

STEPS = [
    STEP_USER,
    STEP_AIS_RESTORE_BACKUP,
    STEP_CORE_CONFIG,
    STEP_INTEGRATION,
    STEP_MOB_INTEGRATION,
]

DEFAULT_AREAS = ("living_room", "kitchen", "bedroom")
