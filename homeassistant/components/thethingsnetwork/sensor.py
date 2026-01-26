"""The Things Network's integration sensors."""

import logging
from typing import Any

from ttn_client import TTNSensorValue

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CONF_APP_ID, DOMAIN
from .entity import TTNEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for TTN."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: set[tuple[str, str]] = set()

    def _async_measurement_listener() -> None:
        data = coordinator.data
        new_sensors = {
            (device_id, field_id): TtnDataSensor(
                coordinator,
                entry.data[CONF_APP_ID],
                ttn_value,
            )
            for device_id, device_uplinks in data.items()
            for field_id, ttn_value in device_uplinks.items()
            if (device_id, field_id) not in sensors
            and isinstance(ttn_value, TTNSensorValue)
        }
        if new_sensors:
            async_add_entities(new_sensors.values())
        sensors.update(new_sensors.keys())

    entry.async_on_unload(coordinator.async_add_listener(_async_measurement_listener))
    _async_measurement_listener()


class TtnDataSensor(TTNEntity, SensorEntity):
    """Represents a TTN Home Assistant Sensor."""

    _ttn_value: TTNSensorValue

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        # The value type can be list at runtime despite type hints
        value: Any = self._ttn_value.value
        # For array values (like Wi-Fi scan data), return count
        if isinstance(value, list):
            return len(value)
        return value  # type: ignore[no-any-return]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes for array values."""
        # The value type can be list at runtime despite type hints
        value: Any = self._ttn_value.value
        if isinstance(value, list) and value:
            attrs: dict[str, Any] = {"items_count": len(value)}

            # Check if this is Wi-Fi scan data (list of dicts with mac/rssi)
            if all(isinstance(item, dict) and "mac" in item for item in value):
                # Create attributes for each access point
                for idx, ap in enumerate(value, 1):
                    attrs[f"ap_{idx}_mac"] = ap.get("mac")
                    attrs[f"ap_{idx}_rssi"] = ap.get("rssi")
            # Handle other dict-based arrays generically
            elif all(isinstance(item, dict) for item in value):
                # Store each item as a JSON string for easy access
                for idx, item in enumerate(value, 1):
                    attrs[f"item_{idx}"] = item
            # Handle simple value arrays (strings, numbers, etc.)
            else:
                for idx, item in enumerate(value, 1):
                    attrs[f"item_{idx}"] = item

            return attrs
        return None
