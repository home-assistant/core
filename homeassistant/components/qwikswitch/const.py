"""Support for Qwikswitch devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from pyqwikswitch.async_ import QSUsb

DOMAIN = "qwikswitch"
DATA_QUIKSWITCH: HassKey[QSUsb] = HassKey(DOMAIN)
