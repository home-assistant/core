"""Constants for Nest Legacy events."""

# This is the global event type that the coordinator fires on the HA event bus.
# Event entities will listen for this event.
NEST_LEGACY_EVENT = "nest_legacy_event"

# These are the event types that the EventEntity can fire, which are used in automations.
EVENT_TYPE_DOORBELL_CHIME = "doorbell_chime"
EVENT_TYPE_CAMERA_MOTION = "camera_motion"
EVENT_TYPE_CAMERA_PERSON = "camera_person"
EVENT_TYPE_CAMERA_SOUND = "camera_sound"
EVENT_TYPE_CAMERA_FACE = "camera_face"
