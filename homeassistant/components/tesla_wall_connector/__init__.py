"""The Tesla Wall Connector integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Callable

from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import (
    WallConnectorConnectionError,
    WallConnectorConnectionTimeoutError,
    WallConnectorError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_SCAN_INTERVAL_CHARGING,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_CHARGING,
    DOMAIN,
    WALLCONNECTOR_CLIENT,
    WALLCONNECTOR_DATA_LIFETIME,
    WALLCONNECTOR_DATA_UPDATE_COORDINATOR,
    WALLCONNECTOR_DATA_VITALS,
    WALLCONNECTOR_DEVICE_NAME,
    WALLCONNECTOR_FIRMWARE_VERSION,
    WALLCONNECTOR_HOST,
    WALLCONNECTOR_PART_NUMBER,
    WALLCONNECTOR_SERIAL_NUMBER,
)

PLATFORMS: list[str] = ["sensor", "binary_sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tesla Wall Connector from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hostname = entry.data[CONF_HOST]
    poll_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    poll_interval_charging = entry.options.get(
        CONF_SCAN_INTERVAL_CHARGING, DEFAULT_SCAN_INTERVAL_CHARGING
    )

    wall_connector = WallConnector(host=hostname, session=async_get_clientsession(hass))

    hass.data[DOMAIN][entry.entry_id] = {
        WALLCONNECTOR_CLIENT: wall_connector,
        WALLCONNECTOR_HOST: hostname,
    }

    try:
        version_data = await wall_connector.async_get_version()
    except WallConnectorError as ex:
        raise ConfigEntryNotReady from ex

    hass.data[DOMAIN][entry.entry_id].update(
        {
            WALLCONNECTOR_PART_NUMBER: version_data.part_number,
            WALLCONNECTOR_FIRMWARE_VERSION: version_data.firmware_version,
            WALLCONNECTOR_SERIAL_NUMBER: version_data.serial_number,
        }
    )

    async def async_update_data():
        """Fetch new data from the Wall Connector."""
        wall_connector = hass.data[DOMAIN][entry.entry_id][WALLCONNECTOR_CLIENT]
        coordinator = hass.data[DOMAIN][entry.entry_id][
            WALLCONNECTOR_DATA_UPDATE_COORDINATOR
        ]

        try:
            previous_contactor_closed = (
                coordinator.data[WALLCONNECTOR_DATA_VITALS].contactor_closed
                if coordinator.data is not None
                and coordinator.data[WALLCONNECTOR_DATA_VITALS] is not None
                else False
            )
            vitals = await wall_connector.async_get_vitals()
            lifetime = await wall_connector.async_get_lifetime()

            if previous_contactor_closed != vitals.contactor_closed:
                coordinator.update_interval = (
                    timedelta(seconds=poll_interval)
                    if not vitals.contactor_closed
                    else timedelta(seconds=poll_interval_charging)
                )
                _LOGGER.debug(
                    "Contactor closed: %s. Update interval: %s",
                    str(vitals.contactor_closed),
                    str(coordinator.update_interval),
                )

        except WallConnectorConnectionTimeoutError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {hostname}: Timeout"
            ) from ex
        except WallConnectorConnectionError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {hostname}: Cannot connect"
            ) from ex
        except WallConnectorError as ex:
            raise UpdateFailed(
                f"Could not fetch data from Tesla WallConnector at {hostname}: {ex}"
            ) from ex

        return {
            WALLCONNECTOR_DATA_VITALS: vitals,
            WALLCONNECTOR_DATA_LIFETIME: lifetime,
        }

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="tesla-wallconnector",
        update_method=async_update_data,
        update_interval=timedelta(seconds=poll_interval),
    )

    hass.data[DOMAIN][entry.entry_id].update(
        {WALLCONNECTOR_DATA_UPDATE_COORDINATOR: coordinator}
    )

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def prefix_entity_name(name: str) -> str:
    """Prefixes entity name."""
    return f"{WALLCONNECTOR_DEVICE_NAME} {name}"


def get_unique_id(serial_number: str, key: str) -> str:
    """Get a unique entity name."""
    return f"{serial_number}-{key}"


class WallConnectorEntity(CoordinatorEntity):
    """Base class for Wall Connector entities."""

    def __init__(self, wall_connector: dict) -> None:
        """Initialize WallConnector Entity."""
        self.wall_connector = wall_connector
        self._attr_unique_id = get_unique_id(
            wall_connector[WALLCONNECTOR_SERIAL_NUMBER], self.entity_description.key
        )
        super().__init__(wall_connector[WALLCONNECTOR_DATA_UPDATE_COORDINATOR])

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.wall_connector[WALLCONNECTOR_SERIAL_NUMBER])},
            default_name=WALLCONNECTOR_DEVICE_NAME,
            model=self.wall_connector[WALLCONNECTOR_PART_NUMBER],
            sw_version=self.wall_connector[WALLCONNECTOR_FIRMWARE_VERSION],
            default_manufacturer="Tesla",
        )


@dataclass()
class WallConnectorLambdaValueGetterMixin:
    """Mixin with a function pointer for getting sensor value."""

    value_fn: Callable[[dict], Any]
