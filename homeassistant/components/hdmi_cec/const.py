"""Support for HDMI CEC."""

from dataclasses import dataclass

from pycec.network import HDMINetwork, PhysicalAddress

from homeassistant.util.hass_dict import HassKey

DOMAIN = "hdmi_cec"

ATTR_NEW = "new"

EVENT_HDMI_CEC_UNAVAILABLE = "hdmi_cec_unavailable"


@dataclass(frozen=True, slots=True)
class HdmiCecData:
    """HDMI CEC network and configured device aliases."""

    hdmi_network: HDMINetwork
    device_aliases: dict[str, PhysicalAddress | list[int]]


DATA_HDMI_CEC: HassKey[HdmiCecData] = HassKey(f"{DOMAIN}_data")
