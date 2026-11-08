"""Support for Guardian services."""

from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from aioguardian.errors import GuardianError
import probatio

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

if TYPE_CHECKING:
    from . import GuardianConfigEntry, GuardianData


class GuardianService(StrEnum):
    """Store keys for Guardian services."""

    PAIR_SENSOR = "pair_sensor"
    UNPAIR_SENSOR = "unpair_sensor"
    UPGRADE_FIRMWARE = "upgrade_firmware"


class GuardianServiceArgument(StrEnum):
    """Store keys for Guardian service arguments."""

    UID = "uid"
    URL = "url"
    PORT = "port"
    FILENAME = "filename"


SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(GuardianServiceArgument.UID): cv.string,
    }
)

SERVICE_UPGRADE_FIRMWARE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Optional(GuardianServiceArgument.URL): cv.url,
        probatio.Optional(GuardianServiceArgument.PORT): probatio.Port(),
        probatio.Optional(GuardianServiceArgument.FILENAME): cv.string,
    },
)


@callback
def async_get_entry_id_for_service_call(call: ServiceCall) -> GuardianConfigEntry:
    """Get the entry ID related to a service call (by device ID)."""
    config_entry: GuardianConfigEntry
    _, config_entry = service.async_get_device_and_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.DEVICE_ID]
    )
    return config_entry


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
    uid = call.data[GuardianServiceArgument.UID]
    await data.client.sensor.pair_sensor(uid)
    await data.paired_sensor_manager.async_pair_sensor(uid)


@call_with_data
async def async_unpair_sensor(call: ServiceCall, data: GuardianData) -> None:
    """Remove a paired sensor."""
    uid = call.data[GuardianServiceArgument.UID]
    await data.client.sensor.unpair_sensor(uid)
    await data.paired_sensor_manager.async_unpair_sensor(uid)


@call_with_data
async def async_upgrade_firmware(call: ServiceCall, data: GuardianData) -> None:
    """Upgrade the device firmware."""
    await data.client.system.upgrade_firmware(
        url=call.data[GuardianServiceArgument.URL],
        port=call.data[GuardianServiceArgument.PORT],
        filename=call.data[GuardianServiceArgument.FILENAME],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the guardian services."""
    for service_name, schema, method in (
        (
            GuardianService.PAIR_SENSOR,
            SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA,
            async_pair_sensor,
        ),
        (
            GuardianService.UNPAIR_SENSOR,
            SERVICE_PAIR_UNPAIR_SENSOR_SCHEMA,
            async_unpair_sensor,
        ),
        (
            GuardianService.UPGRADE_FIRMWARE,
            SERVICE_UPGRADE_FIRMWARE_SCHEMA,
            async_upgrade_firmware,
        ),
    ):
        hass.services.async_register(DOMAIN, service_name, method, schema=schema)
