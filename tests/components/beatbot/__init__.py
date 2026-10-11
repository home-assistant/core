"""Test helpers for the Beatbot integration."""

from typing import Any
from unittest.mock import MagicMock

from beatbot_cloud import (
    BeatbotCapability,
    BeatbotDeviceData,
    BeatbotEvent,
    FirmwareVersion,
)
from beatbot_cloud.const import OAUTH2_TOKEN_URL

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_ID = "pool-cleaner-1"
TOKEN_URL = OAUTH2_TOKEN_URL
STATUS_ENTITY_ID = "sensor.aquasense_status"
BATTERY_ENTITY_ID = "sensor.aquasense_battery"
ERROR_ENTITY_ID = "sensor.aquasense_error"

INTERFACE_STATE = "vacuum.state"
INTERFACE_BATTERY = "vacuum.battery"


def create_device(
    device_id: str = DEVICE_ID,
    *,
    name: str = "AquaSense",
    product_category: str = "pool_clean_bot",
    work_status: int = 5,
    error_code: int = 0,
    battery_level: int = 80,
    is_online: bool = True,
) -> BeatbotDeviceData:
    """Return discovery data for a Beatbot device.

    Mirrors what the library parses out of a discovery response, so entity
    metadata built from it faces the same shapes as in production.
    """
    return BeatbotDeviceData(
        device_id=device_id,
        product_id="product-1",
        product_category=product_category,
        name=name,
        model="AquaSense 2",
        work_status=work_status,
        work_mode=0,
        error_code=error_code,
        battery_level=battery_level,
        versions=[FirmwareVersion(channel=0, version="1.2.3")],
        is_online=is_online,
        work_mode_options={0: "auto", 1: "floor"},
        capabilities={
            INTERFACE_STATE: BeatbotCapability(INTERFACE_STATE, retrievable=True),
            INTERFACE_BATTERY: BeatbotCapability(INTERFACE_BATTERY, retrievable=True),
        },
    )


def batch_state(
    device_id: str = DEVICE_ID,
    states: dict[str, int] | None = None,
    *,
    is_online: bool | None = True,
) -> dict[str, dict[str, object]]:
    """Return a batched state response for one device."""
    return {device_id: {"is_online": is_online, "states": states or {}}}


def property_change(
    interface_info: str, value: object, device_id: str = DEVICE_ID
) -> BeatbotEvent:
    """Return a pushed property change for one device."""
    return BeatbotEvent(
        "1",
        "properties_changed",
        device_id,
        {"interfaceInfo": interface_info, "value": value},
    )


def status_event(online: bool, device_id: str = DEVICE_ID) -> BeatbotEvent:
    """Return a pushed online/offline change for one device."""
    return BeatbotEvent("2", "status", device_id, {"online": online})


def topology_event(
    event_type: str = "device_removed", device_id: str = DEVICE_ID
) -> BeatbotEvent:
    """Return a device-set event that carries no device state."""
    return BeatbotEvent("3", event_type, device_id, None)


def library_callback(mock_event_client: MagicMock, name: str) -> Any:
    """Return a callback the integration registered with the event library."""
    return mock_event_client.call_args.kwargs[name]


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Beatbot integration from a config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
