"""Datacoordinator for InComfort integration."""

from dataclasses import dataclass, field
from datetime import timedelta
from http import HTTPStatus
import logging

from aiohttp import ClientResponseError
from incomfortclient import (
    Gateway as InComfortGateway,
    Heater as InComfortHeater,
    InvalidGateway,
    InvalidHeaterList,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

type InComfortConfigEntry = ConfigEntry[InComfortDataCoordinator]

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 30


@dataclass
class InComfortData:
    """Keep the Intergas InComfort entry data."""

    client: InComfortGateway
    heaters: list[InComfortHeater] = field(default_factory=list)


@callback
def async_cleanup_stale_devices(
    hass: HomeAssistant,
    entry: InComfortConfigEntry,
    data: InComfortData,
    gateway_device: dr.DeviceEntry,
) -> None:
    """Cleanup stale heater devices and climates."""
    heater_serial_numbers = {heater.serial_no for heater in data.heaters}
    device_registry = dr.async_get(hass)
    device_entries = device_registry.devices.get_devices_for_config_entry_id(
        entry.entry_id
    )
    stale_heater_serial_numbers: list[str] = [
        device_entry.serial_number
        for device_entry in device_entries
        if device_entry.id != gateway_device.id
        and device_entry.serial_number is not None
        and device_entry.serial_number not in heater_serial_numbers
    ]
    if not stale_heater_serial_numbers:
        return
    cleanup_devices: list[str] = []
    # Find stale heater and climate devices
    for serial_number in stale_heater_serial_numbers:
        cleanup_list = [f"{serial_number}_{index}" for index in range(1, 4)]
        cleanup_list.append(serial_number)
        cleanup_identifiers = [{(DOMAIN, cleanup_id)} for cleanup_id in cleanup_list]
        cleanup_devices.extend(
            device_entry.id
            for device_entry in device_entries
            if device_entry.identifiers in cleanup_identifiers
        )
    for device_id in cleanup_devices:
        device_registry.async_remove_device(device_id)


class InComfortDataCoordinator(DataUpdateCoordinator[InComfortData]):
    """Data coordinator for InComfort entities."""

    config_entry: InComfortConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: InComfortConfigEntry,
        client: InComfortGateway,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="InComfort datacoordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.client = client
        self.unique_id = config_entry.unique_id

    async def _async_setup(self) -> None:
        """Set up the Incomfort coordinator."""
        try:
            await self.client.heaters()
        except InvalidHeaterList as exc:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="no_heaters",
            ) from exc
        except InvalidGateway as exc:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from exc
        except ClientResponseError as exc:
            if exc.status == HTTPStatus.NOT_FOUND:
                raise ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="not_found",
                ) from exc
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="unknown",
            ) from exc
        except TimeoutError as exc:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="timeout_error",
            ) from exc

    async def _async_update_data(self) -> InComfortData:
        """Fetch data from Incomfort."""
        try:
            heaters = await self.client.heaters()
            for heater in heaters:
                await heater.update()
        except InvalidGateway as exc:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from exc
        except TimeoutError as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_error",
            ) from exc
        except ClientResponseError as exc:
            if exc.status == HTTPStatus.UNAUTHORIZED:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                ) from exc
            _LOGGER.exception("Error communicating with InComfort gateway")
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown",
            ) from exc
        except InvalidHeaterList as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_heaters",
            ) from exc

        incomfort_data = InComfortData(
            client=self.client,
            heaters=heaters,
        )

        # Register discovered gateway device
        # Respect this as it is. Maybe later...
        device_registry = dr.async_get(self.hass)
        gateway_device = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            connections={(dr.CONNECTION_NETWORK_MAC, self.config_entry.unique_id)}
            if self.config_entry.unique_id is not None
            else set(),
            manufacturer="Intergas",
            name="RFGateway",
        )
        async_cleanup_stale_devices(
            self.hass,
            self.config_entry,
            incomfort_data,
            gateway_device,
        )

        return incomfort_data
