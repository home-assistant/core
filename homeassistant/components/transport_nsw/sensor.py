"""Support for Transport NSW (AU) to query next leave event."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from TransportNSW import TransportNSW

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODE, CONF_API_KEY, CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_DELAY,
    ATTR_DESTINATION,
    ATTR_DUE_IN,
    ATTR_REAL_TIME,
    ATTR_ROUTE,
    ATTR_STOP_ID,
    CONF_DESTINATION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
    TRANSPORT_ICONS,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


def _raise_update_failed(message: str, exc: Exception | None = None) -> None:
    """Raise UpdateFailed with the given message."""
    if exc:
        raise UpdateFailed(message) from exc
    raise UpdateFailed(message)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Transport NSW sensor from a config entry."""
    coordinator = TransportNSWCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([TransportNSWSensor(coordinator, config_entry)], True)


class TransportNSWCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Transport NSW data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.api_key = config_entry.data[CONF_API_KEY]
        self.stop_id = config_entry.data[CONF_STOP_ID]
        self.route = config_entry.options.get(CONF_ROUTE, "")
        self.destination = config_entry.options.get(CONF_DESTINATION, "")
        self.transport_nsw = TransportNSW()

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Transport NSW {self.stop_id}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Transport NSW."""
        try:
            data = await self.hass.async_add_executor_job(
                self.transport_nsw.get_departures,
                self.stop_id,
                self.route,
                self.destination,
                self.api_key,
            )

            if data is None:
                _raise_update_failed("No data returned from Transport NSW API")

            return {
                ATTR_ROUTE: _get_value(data.get("route")),
                ATTR_DUE_IN: _get_value(data.get("due")),
                ATTR_DELAY: _get_value(data.get("delay")),
                ATTR_REAL_TIME: _get_value(data.get("real_time")),
                ATTR_DESTINATION: _get_value(data.get("destination")),
                ATTR_MODE: _get_value(data.get("mode")),
            }
        except Exception as exc:  # noqa: BLE001
            _raise_update_failed(
                f"Error communicating with Transport NSW API: {exc}", exc
            )


def _get_value(value):
    """Replace the API response 'n/a' value with None."""
    return None if (value is None or value == "n/a") else value


class TransportNSWSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an Transport NSW sensor."""

    _attr_attribution = "Data provided by Transport NSW"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self, coordinator: TransportNSWCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = config_entry.data[CONF_NAME]
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}"

        # Device info for grouping entities
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.data[CONF_STOP_ID])},
            name=f"Transport NSW Stop {config_entry.data[CONF_STOP_ID]}",
            manufacturer="Transport NSW",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(ATTR_DUE_IN)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self.coordinator.data is None:
            return None

        return {
            ATTR_STOP_ID: self.config_entry.data[CONF_STOP_ID],
            ATTR_ROUTE: self.coordinator.data.get(ATTR_ROUTE),
            ATTR_DELAY: self.coordinator.data.get(ATTR_DELAY),
            ATTR_REAL_TIME: self.coordinator.data.get(ATTR_REAL_TIME),
            ATTR_DESTINATION: self.coordinator.data.get(ATTR_DESTINATION),
            ATTR_MODE: self.coordinator.data.get(ATTR_MODE),
        }

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        if self.coordinator.data is None:
            return TRANSPORT_ICONS[None]
        mode = self.coordinator.data.get(ATTR_MODE)
        return TRANSPORT_ICONS.get(mode, TRANSPORT_ICONS[None])
