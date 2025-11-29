"""Teltonika sensor platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import TeltonikaConfigEntry, TeltonikaData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="rsrp",
        translation_key="rsrp",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="rsrq",
        translation_key="rsrq",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dB",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="sinr",
        translation_key="sinr",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dB",
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="operator",
        translation_key="operator",
    ),
    SensorEntityDescription(
        key="connection_type",
        translation_key="connection_type",
    ),
)


async def async_setup_entry(  # pylint: disable=hass-argument-type
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Teltonika sensor platform."""
    data: TeltonikaData = entry.runtime_data

    # Create sensors for each online modem
    coordinator_data = data.coordinator.data
    if coordinator_data:
        async_add_entities(
            [
                TeltonikaSensorEntity(
                    data.coordinator,
                    data.device_info,
                    description,
                    modem_id,
                    modem,
                )
                for modem_id, modem in coordinator_data.items()
                for description in SENSOR_DESCRIPTIONS
            ]
        )


class TeltonikaSensorEntity(CoordinatorEntity, SensorEntity):
    """Teltonika sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        device_info,
        description: SensorEntityDescription,
        modem_id: str,
        modem: Any,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._modem_id = modem_id
        self._attr_device_info = device_info

        # Create unique ID using entry unique identifier, modem ID, and sensor type
        entry_unique_id = (
            coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        )
        self._attr_unique_id = f"{entry_unique_id}_{modem_id}_{description.key}"

        # Use translation key for proper naming
        modem_name = getattr(modem, "name", f"Modem {modem_id}")
        self._modem_name = modem_name
        self._attr_translation_key = description.translation_key
        self._attr_translation_placeholders = {"modem_name": modem_name}
        self._attr_suggested_object_id = slugify(
            f"{modem_name} {description.translation_key or description.key}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._modem_id not in self.coordinator.data:
            self._attr_available = False
            return

        self._attr_available = True
        modem = self.coordinator.data[self._modem_id]

        # Update native value
        if self.entity_description.key == "connection_type":
            value = getattr(modem, "conntype", None)
        else:
            value = getattr(modem, self.entity_description.key, None)

        # Ensure value is a valid state type
        if isinstance(value, (str, int, float)):
            self._attr_native_value = value
        else:
            self._attr_native_value = None

        # Update extra state attributes
        attrs = {
            "modem_id": self._modem_id,
            "modem_name": getattr(modem, "name", self._modem_name),
            "connection_type": getattr(modem, "conntype", "Unknown"),
            "operator": getattr(modem, "operator", "Unknown"),
        }

        # Add sensor-specific attributes
        if self.entity_description.key in ("rssi", "rsrp", "rsrq", "sinr"):
            band = getattr(modem, "sc_band_av", None) or getattr(
                modem, "band", "Unknown"
            )
            attrs.update(
                {
                    "band": band,
                    "state": getattr(modem, "state", "Unknown"),
                }
            )

        self._attr_extra_state_attributes = attrs
        super()._handle_coordinator_update()
