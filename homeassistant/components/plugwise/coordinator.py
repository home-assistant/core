"""DataUpdateCoordinator for Plugwise."""
from datetime import timedelta

from plugwise import PlugwiseData, Smile
from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    InvalidXMLError,
    ResponseError,
    UnsupportedDeviceError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DEFAULT_USERNAME, DOMAIN, LOGGER


def remove_stale_devices(
    api: Smile,
    device_registry: dr.DeviceRegistry,
    via_id: str,
) -> None:
    """Process the Plugwise devices present in the device_registry connected to a specific Gateway."""
    for dev_id, device_entry in list(device_registry.devices.items()):
        if device_entry.via_device_id == via_id:
            for item in device_entry.identifiers:
                if item[0] == DOMAIN and item[1] in api.device_list:
                    continue

                device_registry.async_remove_device(dev_id)
                LOGGER.debug(
                    "Removed device %s %s %s from device_registry",
                    DOMAIN,
                    device_entry.model,
                    dev_id,
                )


def cleanup_device_registry(
    hass: HomeAssistant,
    api: Smile,
) -> None:
    """Remove deleted devices from device-registry."""
    device_registry = dr.async_get(hass)
    via_id_list: list[list[str]] = []
    # Collect the required data of the Plugwise Gateway's
    for device_entry in list(device_registry.devices.values()):
        if device_entry.manufacturer == "Plugwise" and device_entry.model == "Gateway":
            for item in device_entry.identifiers:
                via_id_list.append([item[1], device_entry.id])

    for via_id in via_id_list:
        if via_id[0] != api.gateway_id:
            continue  # pragma: no cover

        remove_stale_devices(api, device_registry, via_id[1])


class PlugwiseDataUpdateCoordinator(DataUpdateCoordinator[PlugwiseData]):
    """Class to manage fetching Plugwise data from single endpoint."""

    _connected: bool = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            # Don't refresh immediately, give the device time to process
            # the change in state before we query it.
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=1.5,
                immediate=False,
            ),
        )

        self.api = Smile(
            host=entry.data[CONF_HOST],
            username=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
            password=entry.data[CONF_PASSWORD],
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
            timeout=30,
            websession=async_get_clientsession(hass, verify_ssl=False),
        )
        self.hass = hass
        self.update_interval = DEFAULT_SCAN_INTERVAL.get(
            str(self.api.smile_type), timedelta(seconds=60)
        )

    async def _connect(self) -> None:
        """Connect to the Plugwise Smile."""
        self._connected = await self.api.connect()
        self.api.get_all_devices()

    async def _async_update_data(self) -> PlugwiseData:
        """Fetch data from Plugwise."""

        try:
            if not self._connected:
                await self._connect()
            data = await self.api.async_update()
        except InvalidAuthentication as err:
            raise ConfigEntryError("Invalid username or Smile ID") from err
        except (InvalidXMLError, ResponseError) as err:
            raise UpdateFailed(
                "Invalid XML data, or error indication received for the Plugwise"
                " Adam/Smile/Stretch"
            ) from err
        except UnsupportedDeviceError as err:
            raise ConfigEntryError("Device with unsupported firmware") from err
        except ConnectionFailedError as err:
            raise UpdateFailed("Failed to connect to the Plugwise Smile") from err

        # Clean-up removed devices
        cleanup_device_registry(self.hass, self.api)

        return data
