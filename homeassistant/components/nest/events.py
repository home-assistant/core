"""Library from Pub/sub messages, events and device triggers."""

from google_nest_sdm.camera_traits import (
    CameraMotionTrait,
    CameraPersonTrait,
    CameraSoundTrait,
)
from google_nest_sdm.doorbell_traits import DoorbellChimeTrait
from google_nest_sdm.event import (
    CameraMotionEvent,
    CameraPersonEvent,
    CameraSoundEvent,
    DoorbellChimeEvent,
)

NEST_EVENT = "nest_event"
# The nest_event namespace will fire events that are triggered from messages
# received via the Pub/Sub subscriber.
#
# An example event payload:
#
# {
#   "event_type": "nest_event"
#   "data": {
#       "device_id": "my-device-id",
#       "type": "camera_motion",
#       "timestamp": "2021-10-24T19:42:43.304000+00:00",
#       "nest_event_id": "KcO1HIR9sPKQ2bqby_vTcCcEov...",
#       "zones": ["Zone 1"],
#   },
#   ...
# }
#
# The nest_event_id corresponds to the event id in the SDM API used to retrieve
# snapshots.
#
# The following event types are fired:
EVENT_DOORBELL_CHIME = "doorbell_chime"
EVENT_CAMERA_MOTION = "camera_motion"
EVENT_CAMERA_PERSON = "camera_person"
EVENT_CAMERA_SOUND = "camera_sound"

# Mapping of supported device traits to home assistant event types.  Devices
# that support these traits will generate Pub/Sub event messages in
# the EVENT_NAME_MAP
DEVICE_TRAIT_TRIGGER_MAP = {
    DoorbellChimeTrait.NAME: EVENT_DOORBELL_CHIME,
    CameraMotionTrait.NAME: EVENT_CAMERA_MOTION,
    CameraPersonTrait.NAME: EVENT_CAMERA_PERSON,
    CameraSoundTrait.NAME: EVENT_CAMERA_SOUND,
}

# Mapping of incoming SDM Pub/Sub event message types to the home assistant
# event type to fire.
EVENT_NAME_MAP = {
    DoorbellChimeEvent.NAME: EVENT_DOORBELL_CHIME,
    CameraMotionEvent.NAME: EVENT_CAMERA_MOTION,
    CameraPersonEvent.NAME: EVENT_CAMERA_PERSON,
    CameraSoundEvent.NAME: EVENT_CAMERA_SOUND,
}

# Names for event types shown in the media source
MEDIA_SOURCE_EVENT_TITLE_MAP = {
    DoorbellChimeEvent.NAME: "Doorbell",
    CameraMotionEvent.NAME: "Motion",
    CameraPersonEvent.NAME: "Person",
    CameraSoundEvent.NAME: "Sound",
}
