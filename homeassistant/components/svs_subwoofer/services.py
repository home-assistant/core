"""Services for SVS Subwoofer integration."""

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_LOAD_PRESET,
    SERVICE_SET_VOLUME,
    SERVICE_SYNC_FROM,
    SYNCABLE_PARAMS,
    VOLUME_MAX,
    VOLUME_MIN,
)
from .helpers import get_coordinator_for_device

ATTR_SOURCE_DEVICE_ID = "source_device_id"
ATTR_TARGET_DEVICE_IDS = "target_device_ids"
ATTR_DEVICE_IDS = "device_ids"
ATTR_VOLUME = "volume"
ATTR_OFFSETS = "offsets"
ATTR_PRESET = "preset"

SERVICE_SYNC_FROM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SOURCE_DEVICE_ID): cv.string,
        vol.Required(ATTR_TARGET_DEVICE_IDS): vol.All(cv.ensure_list, [cv.string]),
    }
)

SERVICE_SET_VOLUME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_IDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(min=VOLUME_MIN, max=VOLUME_MAX)
        ),
        vol.Optional(ATTR_OFFSETS, default={}): {cv.string: vol.Coerce(int)},
    }
)

SERVICE_LOAD_PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_IDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_PRESET): vol.Any(
            vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
            vol.In(["1", "2", "3", "4", "Default", "default"]),
        ),
    }
)


def _coordinator_or_raise(hass: HomeAssistant, device_id: str):
    """Resolve a device_id to a coordinator, or raise ServiceValidationError."""
    coordinator = get_coordinator_for_device(hass, device_id)
    if coordinator is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )
    return coordinator


async def _async_sync_from(hass: HomeAssistant, call: ServiceCall) -> None:
    """Copy all settings from source subwoofer to target subwoofer(s)."""
    source = _coordinator_or_raise(hass, call.data[ATTR_SOURCE_DEVICE_ID])
    targets = [
        _coordinator_or_raise(hass, target_id)
        for target_id in call.data[ATTR_TARGET_DEVICE_IDS]
    ]

    for target in targets:
        for param in SYNCABLE_PARAMS:
            value = source.data.get(param)
            if value is None:
                continue
            await target.async_send_command(param, value)


async def _async_set_volume(hass: HomeAssistant, call: ServiceCall) -> None:
    """Set volume on multiple subwoofers with optional per-device offsets."""
    base_volume: int = call.data[ATTR_VOLUME]
    offsets: dict[str, int] = call.data.get(ATTR_OFFSETS, {})

    for device_id in call.data[ATTR_DEVICE_IDS]:
        coordinator = _coordinator_or_raise(hass, device_id)
        volume = max(
            VOLUME_MIN, min(VOLUME_MAX, base_volume + offsets.get(device_id, 0))
        )
        await coordinator.async_send_command("VOLUME", volume)


async def _async_load_preset(hass: HomeAssistant, call: ServiceCall) -> None:
    """Load preset on multiple subwoofers."""
    preset = call.data[ATTR_PRESET]
    # Schema coerces "1"-"4" to int; only "Default"/"default" arrive as str.
    preset_num = 4 if isinstance(preset, str) else preset
    for device_id in call.data[ATTR_DEVICE_IDS]:
        coordinator = _coordinator_or_raise(hass, device_id)
        await coordinator.async_load_preset(preset_num)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration-wide services."""

    async def handle_sync_from(call: ServiceCall) -> None:
        await _async_sync_from(hass, call)

    async def handle_set_volume(call: ServiceCall) -> None:
        await _async_set_volume(hass, call)

    async def handle_load_preset(call: ServiceCall) -> None:
        await _async_load_preset(hass, call)

    hass.services.async_register(
        DOMAIN, SERVICE_SYNC_FROM, handle_sync_from, schema=SERVICE_SYNC_FROM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_VOLUME, handle_set_volume, schema=SERVICE_SET_VOLUME_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOAD_PRESET,
        handle_load_preset,
        schema=SERVICE_LOAD_PRESET_SCHEMA,
    )
