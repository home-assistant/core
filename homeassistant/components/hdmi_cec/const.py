"""Support for HDMI CEC."""

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .services import HdmiCecData

DOMAIN = "hdmi_cec"

ATTR_NEW = "new"

EVENT_HDMI_CEC_UNAVAILABLE = "hdmi_cec_unavailable"

DATA_HDMI_CEC: HassKey[HdmiCecData] = HassKey(f"{DOMAIN}_data")
