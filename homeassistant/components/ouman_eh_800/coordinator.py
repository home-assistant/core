"""Data update coordinator for the Ouman EH-800 integration."""

from datetime import timedelta
import logging
from typing import override

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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN, OumanDevice

_LOGGER = logging.getLogger(__name__)

type OumanEh800ConfigEntry = ConfigEntry[OumanEh800Coordinator]


class OumanEh800Coordinator(DataUpdateCoordinator[dict[OumanEndpoint, OumanValues]]):
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

        entry_id = config_entry.entry_id
        self._main_device_identifier = (DOMAIN, entry_id)
        self._device_info: dict[OumanDevice, DeviceInfo] = {
            OumanDevice.MAIN: DeviceInfo(
                identifiers={self._main_device_identifier},
                manufacturer="Ouman",
                model="EH-800",
                configuration_url=config_entry.data[CONF_URL],
            ),
            OumanDevice.L1: DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_{OumanDevice.L1}")},
                translation_key="heating_circuit",
                translation_placeholders={"circuit_number": "1"},
            ),
            OumanDevice.L2: DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_{OumanDevice.L2}")},
                translation_key="heating_circuit",
                translation_placeholders={"circuit_number": "2"},
            ),
        }

    def device_info(self, device: OumanDevice) -> DeviceInfo:
        """Return the device info for a logical device."""
        device_info = self._device_info[device]
        if device is not OumanDevice.MAIN and "via_device_id" not in device_info:
            device_info["via_device_id"] = dr.async_get_device_id_by_identifier(
                self.hass,
                self._main_device_identifier,
                config_entry_id=self.config_entry.entry_id,
            )
        return device_info

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
    async def _async_update_data(self) -> dict[OumanEndpoint, OumanValues]:
        """Fetch registry values from the device."""
        try:
            return await self.client.get_values(self._registry_set)
        except OumanClientCommunicationError as err:
            raise UpdateFailed("Error communicating with API") from err

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

        self.async_set_updated_data({**self.data, endpoint: result})
        # Separate refresh on all endpoints to catch cascading changes.
        await self.async_request_refresh()

    def sync_circuit_device_names(self) -> None:
        """Set the device-reported circuit names for the L1/L2 sub-device names.

        Should be called after the data update so that platforms register
        L1/L2 devices with the resolved names.
        """
        for device, endpoint, circuit_number in (
            (OumanDevice.L1, L1BaseEndpoints.CIRCUIT_NAME, "1"),
            (OumanDevice.L2, L2BaseEndpoints.CIRCUIT_NAME, "2"),
        ):
            if circuit_name := self.data.get(endpoint):
                assert isinstance(circuit_name, str)
                device_info = self._device_info[device]
                device_info["translation_key"] = "heating_circuit_with_name"
                device_info["translation_placeholders"] = {
                    "circuit_number": circuit_number,
                    "circuit_name": circuit_name,
                }
