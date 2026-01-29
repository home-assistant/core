"""Constants for the Sleep as Android integration."""

DOMAIN = "sleep_as_android"

ATTR_EVENT = "event"
ATTR_VALUE1 = "value1"
ATTR_VALUE2 = "value2"
ATTR_VALUE3 = "value3"

MAP_EVENTS = {
    "sleep_tracking_paused": "paused",
    "sleep_tracking_resumed": "resumed",
    "sleep_tracking_started": "started",
    "sleep_tracking_stopped": "stopped",
    "alarm_alert_dismiss": "alert_dismiss",
    "alarm_alert_start": "alert_start",
    "alarm_rescheduled": "rescheduled",
    "alarm_skip_next": "skip_next",
    "alarm_snooze_canceled": "snooze_canceled",
    "alarm_snooze_clicked": "snooze_clicked",
    "alarm_wake_up_check": "wake_up_check",
    "sound_event_baby": "baby",
    "sound_event_cough": "cough",
    "sound_event_laugh": "laugh",
    "sound_event_snore": "snore",
    "sound_event_talk": "talk",
    "lullaby_start": "start",
    "lullaby_stop": "stop",
    "lullaby_volume_down": "volume_down",
}

ALARM_LABEL_DEFAULT = "alarm"
