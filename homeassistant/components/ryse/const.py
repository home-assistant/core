"""Constants for the RYSE integration."""

from collections.abc import Callable

from homeassistant.util.hass_dict import HassKey

DOMAIN = "ryse"
MANUFACTURER_NAME = "RYSE"
SERVICE_UUID = "a72f2800-b0bd-498b-b4cd-4a3901388238"
MANUFACTURER_ID = 1033
DATA_LOCAL_WAITERS: HassKey[dict[str, Callable[[], None]]] = HassKey(
    f"{DOMAIN}_local_waiters"
)
