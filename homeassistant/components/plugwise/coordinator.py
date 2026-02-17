"""DataUpdateCoordinator for Plugwise."""

from packaging.version import Version
from plugwise import GwEntityData, Smile
from plugwise.exceptions import (
    ConnectionFailedError,
    InvalidAuthentication,
    InvalidSetupError,
    InvalidXMLError,
    PlugwiseError,
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

from .const import (
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    LOGGER,
    P1_UPDATE_INTERVAL,
)

type PlugwiseConfigEntry = ConfigEntry[PlugwiseDataUpdateCoordinator]


class PlugwiseDataUpdateCoordinator(DataUpdateCoordinator[dict[str, GwEntityData]]):
    """Class to manage fetching Plugwise data from single endpoint."""

    _connected: bool = False
    _current_devices: set[str]
    _stored_devices: set[str]
    new_devices: set[str]

    config_entry: PlugwiseConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: PlugwiseConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
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
            websession=async_get_clientsession(hass, verify_ssl=False),
        )
        self._current_devices = set()
        self._stored_devices = set()
        self.new_devices = set()

    async def _connect(self) -> None:
        """Connect to the Plugwise Smile.

        A Version object is received when the connection succeeds.
        """
        version = await self.api.connect()
        self._connected = isinstance(version, Version)
        if self._connected and self.api.smile.type == "power":
            self.update_interval = P1_UPDATE_INTERVAL

    async def _async_setup(self) -> None:
        """Initialize the update_data process."""
        device_reg = dr.async_get(self.hass)
        device_entries = dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        )
        self._stored_devices = {
            identifier[1]
            for device_entry in device_entries
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        }

    async def _async_update_data(self) -> dict[str, GwEntityData]:
        """Fetch data from Plugwise."""
        try:
            if not self._connected:
                await self._connect()
            data = await self.api.async_update()
        except ConnectionFailedError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="failed_to_connect",
            ) from err
        except InvalidAuthentication as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except InvalidSetupError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_setup",
            ) from err
        except (InvalidXMLError, ResponseError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="response_error",
            ) from err
        except PlugwiseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="data_incomplete_or_missing",
            ) from err
        except UnsupportedDeviceError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_firmware",
            ) from err

        self._async_add_remove_devices(data)
        return data

    def _async_add_remove_devices(self, data: dict[str, GwEntityData]) -> None:
        """Add new Plugwise devices, remove non-existing devices."""
        set_of_data = set(data)
        # Check for new or removed devices,
        # 'new_devices' contains all devices present in 'data' at init ('self._current_devices' is empty)
        # this is required for the proper initialization of all the present platform entities.
        self.new_devices = set_of_data - self._current_devices
        current_devices = (
            self._stored_devices if not self._current_devices else self._current_devices
        )
        self._current_devices = set_of_data
        if current_devices - set_of_data:  # device(s) to remove
            self._async_remove_devices(data)

    def _async_remove_devices(self, data: dict[str, GwEntityData]) -> None:
        """Clean registries when removed devices found."""
        device_reg = dr.async_get(self.hass)
        device_list = dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        )

        # First find the Plugwise via_device
        gateway_device = device_reg.async_get_device({(DOMAIN, self.api.gateway_id)})
        assert gateway_device is not None
        via_device_id = gateway_device.id
        # Then remove the connected orphaned device(s)
        for device_entry in device_list:
            for identifier in device_entry.identifiers:
                if (
                    identifier[0] == DOMAIN
                    and device_entry.via_device_id == via_device_id
                    and identifier[1] not in data
                ):
                    device_reg.async_update_device(
                        device_entry.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
                    LOGGER.debug(
                        "Removed %s device/zone %s %s from device_registry",
                        DOMAIN,
                        device_entry.model,
                        identifier[1],
                    )
