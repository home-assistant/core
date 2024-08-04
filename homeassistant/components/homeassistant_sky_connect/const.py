"""Constants for the Home Assistant SkyConnect integration."""

import dataclasses
import enum
from typing import Self

DOMAIN = "homeassistant_sky_connect"
DOCS_WEB_FLASHER_URL = "https://skyconnect.home-assistant.io/firmware-update/"


@dataclasses.dataclass(frozen=True)
class VariantInfo:
    """Hardware variant information."""

    usb_product_name: str
    short_name: str
    full_name: str


class HardwareVariant(VariantInfo, enum.Enum):
    """Hardware variants."""

    SKYCONNECT = (
        "SkyConnect v1.0",
        "SkyConnect",
        "Home Assistant SkyConnect",
    )

    CONNECT_ZBT1 = (
        "Home Assistant Connect ZBT-1",
        "Connect ZBT-1",
        "Home Assistant Connect ZBT-1",
    )

    @classmethod
    def from_usb_product_name(cls, usb_product_name: str) -> Self:
        """Get the hardware variant from the USB product name."""
        for variant in cls:
            if variant.value.usb_product_name == usb_product_name:
                return variant

        raise ValueError(f"Unknown SkyConnect product name: {usb_product_name}")
