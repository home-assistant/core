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
        self._connected: bool = False
        self._current_devices: set[str] = set()
        self._firmware_list: dict[str, str | None] = {}
        self._stored_devices: set[str] = set()
        self.new_devices: set[str] = set()

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

        self._add_remove_devices(data)
        self._update_device_firmware(data)
        return data

    def _add_remove_devices(self, data: dict[str, GwEntityData]) -> None:
        """Add new Plugwise devices, remove non-existing devices."""
        set_of_data = set(data)
        # Check for new or removed devices,
        # 'new_devices' contains all devices present in 'data' at init ('self._current_devices' is empty)
        # this is required for the proper initialization of all the present platform entities.
        self.new_devices = set_of_data - self._current_devices
        for device_id in self.new_devices:
            self._firmware_list.setdefault(device_id, data[device_id].get("firmware"))

        current_devices = (
            self._stored_devices if not self._current_devices else self._current_devices
        )
        self._current_devices = set_of_data
        if removed_devices := (current_devices - set_of_data):  # device(s) to remove
            self._remove_devices(removed_devices)

    def _remove_devices(self, removed_devices: set[str]) -> None:
        """Clean registries when removed devices found."""
        device_reg = dr.async_get(self.hass)
        for device_id in removed_devices:
            if (
                device_entry := device_reg.async_get_device({(DOMAIN, device_id)})
            ) is not None:
                device_reg.async_update_device(
                    device_entry.id, remove_config_entry_id=self.config_entry.entry_id
                )
                LOGGER.debug(
                    "%s %s %s removed from device_registry",
                    DOMAIN,
                    device_entry.model,
                    device_id,
                )

            self._firmware_list.pop(device_id, None)

    def _update_device_firmware(self, data: dict[str, GwEntityData]) -> None:
        """Detect firmware changes and update the device registry."""
        for device_id, device in data.items():
            # Only update firmware when the key is present and not None, to avoid
            # wiping stored firmware on partial or transient updates.
            if "firmware" not in device:
                continue
            new_firmware = device.get("firmware")
            if new_firmware is None:
                continue
            if (
                device_id in self._firmware_list
                and new_firmware != self._firmware_list[device_id]
            ):
                updated = self._update_firmware_in_dr(device_id, new_firmware)
                if updated:
                    self._firmware_list[device_id] = new_firmware

    def _update_firmware_in_dr(self, device_id: str, firmware: str | None) -> bool:
        """Update device sw_version in device_registry."""
        device_reg = dr.async_get(self.hass)
        if (
            device_entry := device_reg.async_get_device({(DOMAIN, device_id)})
        ) is not None:
            device_reg.async_update_device(device_entry.id, sw_version=firmware)
            LOGGER.debug(
                "Firmware in device_registry updated for %s %s %s",
                DOMAIN,
                device_entry.model,
                device_id,
            )
            return True

        return False  # pragma: no cover
