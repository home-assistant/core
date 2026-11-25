"""Validate device availability for LoRaWAN device integration config flows."""

from collections.abc import Callable

from lorawan_connection import (
    Connection,
    ConnectionUnavailable,
    Device,
    DeviceCollection,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .connection import DATA_REGISTRY


class NoConnectionsError(HomeAssistantError):
    """No LoRaWAN connection is available to check for devices."""


class NoSupportedDevicesError(HomeAssistantError):
    """The available LoRaWAN connections contain no supported devices."""


async def async_validate_devices[DeviceT: Device](
    hass: HomeAssistant,
    *,
    create_collection: Callable[[Connection], DeviceCollection[DeviceT]],
    is_supported: Callable[[DeviceT], bool] | None = None,
) -> None:
    """Require a supported device, then release all temporary collections.

    Raise NoConnectionsError if no connection can be checked, or
    NoSupportedDevicesError if none of the checked connections has a match.
    """
    connection_checked = False
    for registered in tuple(hass.data[DATA_REGISTRY].connections.values()):
        collection = create_collection(registered.connection)
        try:
            await collection.async_setup()
        except ConnectionUnavailable:
            continue
        else:
            connection_checked = True
            if any(
                is_supported is None or is_supported(device)
                for device in collection.devices.values()
            ):
                return
        finally:
            collection.close()
    if not connection_checked:
        raise NoConnectionsError
    raise NoSupportedDevicesError
