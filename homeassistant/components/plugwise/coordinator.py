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

from .const import DEFAULT_PORT, DEFAULT_USERNAME, DOMAIN, GATEWAY_ID, LOGGER


async def cleanup_device_and_entity_registry(
    data: PlugwiseData,
    device_reg: dr.DeviceRegistry,
    device_list: list[dr.DeviceEntry],
    entry: ConfigEntry,
) -> None:
    """Remove deleted devices from device- and entity-registry."""
    if len(device_list) - len(data.devices.keys()) <= 0:
        return

    # via_device cannot be None, this will result in the deletion
    # of other Plugwise Gateways when present!
    via_device: str = ""
    for device_entry in device_list:
        if not device_entry.identifiers:
            continue

        item = list(list(device_entry.identifiers)[0])
        if item[0] != DOMAIN:
            continue

        # First find the Plugwise via_device, this is always the first device
        if item[1] == data.gateway[GATEWAY_ID]:
            via_device = device_entry.id
        elif (  # then remove the connected orphaned device(s)
            device_entry.via_device_id == via_device and item[1] not in data.devices
        ):
            device_reg.async_update_device(
                device_entry.id, remove_config_entry_id=entry.entry_id
            )
            LOGGER.debug(
                "Removed %s device %s %s from device_registry",
                DOMAIN,
                device_entry.model,
                item[1],
            )


class PlugwiseDataUpdateCoordinator(DataUpdateCoordinator[PlugwiseData]):
    """Class to manage fetching Plugwise data from single endpoint."""

    _connected: bool = False

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
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
            host=self.config_entry.data[CONF_HOST],
            username=self.config_entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
            password=self.config_entry.data[CONF_PASSWORD],
            port=self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
            timeout=30,
            websession=async_get_clientsession(hass, verify_ssl=False),
        )
        self.device_list: list[dr.DeviceEntry] = []
        self.new_devices: bool = False

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

        device_reg = dr.async_get(self.hass)
        device_list = dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        )

        await cleanup_device_and_entity_registry(
            data, device_reg, device_list, self.config_entry
        )

        self.new_devices = len(data.devices.keys()) - len(self.device_list) > 0
        self.device_list = device_list

        return data
