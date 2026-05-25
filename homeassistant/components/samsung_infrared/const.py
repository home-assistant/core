"""Constants for the Samsung IR integration."""

from enum import StrEnum

from infrared_protocols.codes.samsung.tv import SamsungTVCode

DOMAIN = "samsung_infrared"
CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"
CONF_DEVICE_TYPE = "device_type"


class SamsungDeviceType(StrEnum):
    """Samsung device types."""

    TV = "tv"


SOURCE_MAP: dict[str, SamsungTVCode] = {
    "tv": SamsungTVCode.TV,
    "hdmi_1": SamsungTVCode.HDMI_1,
    "hdmi_2": SamsungTVCode.HDMI_2,
    "hdmi_3": SamsungTVCode.HDMI_3,
    "hdmi_4": SamsungTVCode.HDMI_4,
}

SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "tv": "TV",
    "hdmi_1": "HDMI 1",
    "hdmi_2": "HDMI 2",
    "hdmi_3": "HDMI 3",
    "hdmi_4": "HDMI 4",
}
