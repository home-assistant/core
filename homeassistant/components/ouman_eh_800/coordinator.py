"""Data update coordinator for the Ouman EH-800 integration."""

from dataclasses import dataclass, replace
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from ouman_eh_800_api import (
    ControllableEndpoint,
    L1BaseEndpoints,
    L2BaseEndpoints,
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
    OumanClientError,
    OumanEh800Client,
    OumanEndpoint,
    OumanRegistrySet,
    OumanValues,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN, OumanDevice

_LOGGER = logging.getLogger(__name__)

type OumanEh800ConfigEntry = ConfigEntry[OumanEh800Coordinator]


@dataclass
class OumanEh800Data:
    """Data fetched from the device on each update."""

    values: dict[OumanEndpoint, OumanValues]
    l1_summer_function_active: bool


class OumanEh800Coordinator(DataUpdateCoordinator[OumanEh800Data]):
    """Ouman EH-800 data update coordinator."""

    _registry_set: OumanRegistrySet
    config_entry: OumanEh800ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OumanEh800ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ouman EH-800",
            config_entry=config_entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
            always_update=False,
        )
        self.client: OumanEh800Client = OumanEh800Client(
            session=async_get_clientsession(hass),
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            address=config_entry.data[CONF_URL],
        )

        self.main_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Ouman",
            model="EH-800",
            configuration_url=config_entry.data[CONF_URL],
        )
        self._circuit_device_info: dict[OumanDevice, ChildDeviceInfo] = {}

    def device_info(self, device: OumanDevice) -> DeviceInfo | ChildDeviceInfo:
        """Return the device info for a logical device."""
        if device is OumanDevice.MAIN:
            return self.main_device_info
        return self._circuit_device_info[device]

    @override
    async def _async_setup(self) -> None:
        try:
            # Even though not required to fetch values, perform login once
            # at the start to verify that the credentials are valid.
            await self.client.login()
            self._registry_set = await self.client.get_active_registries()
        except OumanClientAuthenticationError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except OumanClientCommunicationError as err:
            raise ConfigEntryNotReady("Error communicating with API") from err

    @override
    async def _async_update_data(self) -> OumanEh800Data:
        """Fetch registry values and the summer function state from the device."""
        try:
            values = await self.client.get_values(self._registry_set)
            summer_function_active = (
                await self.client.get_is_l1_summer_function_active()
            )
        except OumanClientCommunicationError as err:
            raise UpdateFailed("Error communicating with API") from err
        except OumanClientError as err:
            raise UpdateFailed("Unexpected response from device") from err
        return OumanEh800Data(values, summer_function_active)

    async def async_set_endpoint_value(
        self, endpoint: ControllableEndpoint, value: OumanValues | int
    ) -> None:
        """Set a value on the device and refresh."""
        try:
            result = await self.client.set_endpoint_value(endpoint, value)
        except OumanClientAuthenticationError as err:
            # Reload the config entry; setup re-validates the credentials and
            # starts a reauth flow if they are no longer valid.
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            raise HomeAssistantError("Authentication failed") from err
        except OumanClientCommunicationError as err:
            raise HomeAssistantError("Error communicating with API") from err
        except OumanClientError as err:
            raise HomeAssistantError("Unexpected response from device") from err

        self.async_set_updated_data(
            replace(self.data, values={**self.data.values, endpoint: result})
        )
        # Separate refresh on all endpoints to catch cascading changes.
        await self.async_request_refresh()

    def set_up_circuit_devices(self, parent_device_id: str) -> None:
        """Build child device infos for the active circuits.

        The devices are named after the reported circuit names, so this must
        be called after the first data update and before the platforms are
        set up.
        """
        for device, endpoint, circuit_number in (
            (OumanDevice.L1, L1BaseEndpoints.CIRCUIT_NAME, "1"),
            (OumanDevice.L2, L2BaseEndpoints.CIRCUIT_NAME, "2"),
        ):
            # An absent circuit name means the circuit is inactive.
            if (circuit_name := self.data.values.get(endpoint)) is None:
                continue
            if TYPE_CHECKING:
                assert isinstance(circuit_name, str)
            translation_key = "heating_circuit"
            translation_placeholders = {"circuit_number": circuit_number}
            if circuit_name:
                translation_key = "heating_circuit_with_name"
                translation_placeholders["circuit_name"] = circuit_name
            self._circuit_device_info[device] = ChildDeviceInfo(
                identifiers={(DOMAIN, f"{self.config_entry.entry_id}_{device}")},
                parent_device_id=parent_device_id,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )
