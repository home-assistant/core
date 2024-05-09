"""Constants for the Intent integration."""

DOMAIN = "intent"

TIMER_DATA = f"{DOMAIN}.timer"

ATTR_SECONDS_LEFT = "seconds_left"
ATTR_START_HOURS = "start_hours"
ATTR_START_MINUTES = "start_minutes"
ATTR_START_SECONDS = "start_seconds"

EVENT_INTENT_TIMER_STARTED = f"{DOMAIN}.timer_started"
EVENT_INTENT_TIMER_CANCELLED = f"{DOMAIN}.timer_cancelled"
EVENT_INTENT_TIMER_UPDATED = f"{DOMAIN}.timer_updated"
EVENT_INTENT_TIMER_FINISHED = f"{DOMAIN}.timer_finished"
