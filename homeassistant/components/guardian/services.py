"""Support for Guardian services."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_FILENAME,
    CONF_PORT,
    CONF_URL,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import CONF_UID, DOMAIN

if TYPE_CHECKING:
    from . import GuardianConfigEntry, GuardianData

SERVICE_NAME_PAIR_SENSOR = "pair_sensor"
SERVICE_NAME_UNPAIR_SENSOR = "unpair_sensor"
SERVICE_NAME_UPGRADE_FIRMWARE = "upgrade_firmware"

SERVICES = (
    SERVICE_NAME_PAIR_SENSOR,
    SERVICE_NAME_UNPAIR_SENSOR,
    SERVICE_NAME_UPGRADE_FIRMWARE,
)

SERVICE_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)

SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(CONF_UID): cv.string,
    }
)

SERVICE_UPGRADE_FIRMWARE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(CONF_URL): cv.url,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_FILENAME): cv.string,
    },
)


@callback
def async_get_entry_id_for_service_call(call: ServiceCall) -> GuardianConfigEntry:
    """Get the entry ID related to a service call (by device ID)."""
    device_id = call.data[CONF_DEVICE_ID]
    device_registry = dr.async_get(call.hass)

    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ValueError(f"Invalid Guardian device ID: {device_id}")

    for entry_id in device_entry.config_entries:
        if (entry := call.hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN:
            return entry

    raise ValueError(f"No config entry for device ID: {device_id}")


@callback
def call_with_data(
    func: Callable[[ServiceCall, GuardianData], Coroutine[Any, Any, None]],
) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
    """Hydrate a service call with the appropriate GuardianData object."""

    async def wrapper(call: ServiceCall) -> None:
        """Wrap the service function."""
        data = async_get_entry_id_for_service_call(call).runtime_data

        try:
            async with data.client:
                await func(call, data)
        except GuardianError as err:
            raise HomeAssistantError(
                f"Error while executing {func.__name__}: {err}"
            ) from err

    return wrapper


@call_with_data
async def async_pair_sensor(call: ServiceCall, data: GuardianData) -> None:
    """Add a new paired sensor."""
    uid = call.data[CONF_UID]
    await data.client.sensor.pair_sensor(uid)
    await data.paired_sensor_manager.async_pair_sensor(uid)


@call_with_data
async def async_unpair_sensor(call: ServiceCall, data: GuardianData) -> None:
    """Remove a paired sensor."""
    uid = call.data[CONF_UID]
    await data.client.sensor.unpair_sensor(uid)
    await data.paired_sensor_manager.async_unpair_sensor(uid)


@call_with_data
async def async_upgrade_firmware(call: ServiceCall, data: GuardianData) -> None:
    """Upgrade the device firmware."""
    await data.client.system.upgrade_firmware(
        url=call.data[CONF_URL],
        port=call.data[CONF_PORT],
        filename=call.data[CONF_FILENAME],
    )


def setup_services(hass: HomeAssistant) -> None:
    """Register the Renault services."""
    for service_name, schema, method in (
        (
            SERVICE_NAME_PAIR_SENSOR,
            SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA,
            async_pair_sensor,
        ),
        (
            SERVICE_NAME_UNPAIR_SENSOR,
            SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA,
            async_unpair_sensor,
        ),
        (
            SERVICE_NAME_UPGRADE_FIRMWARE,
            SERVICE_UPGRADE_FIRMWARE_SCHEMA,
            async_upgrade_firmware,
        ),
    ):
        hass.services.async_register(DOMAIN, service_name, method, schema=schema)
