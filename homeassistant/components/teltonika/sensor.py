"""Teltonika sensor platform."""

from __future__ import annotations

import logging

from teltasync.modems import ModemStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TeltonikaConfigEntry, TeltonikaData, TeltonikaDataUpdateCoordinator

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Teltonika sensor platform."""
    data: TeltonikaData = entry.runtime_data
    coordinator = data.coordinator

    # Track known modems to detect new ones
    known_modems: set[str] = set()

    @callback
    def _async_add_new_modems() -> None:
        """Add sensors for newly discovered modems."""
        current_modems = set(coordinator.data.keys())
        new_modems = current_modems - known_modems

        if new_modems:
            entities = [
                TeltonikaSensorEntity(
                    coordinator,
                    data.device_info,
                    description,
                    modem_id,
                    coordinator.data[modem_id],
                )
                for modem_id in new_modems
                for description in SENSOR_DESCRIPTIONS
            ]
            async_add_entities(entities)
            known_modems.update(new_modems)

    # Add sensors for initial modems
    _async_add_new_modems()

    # Listen for new modems
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_modems))


class TeltonikaSensorEntity(
    CoordinatorEntity[TeltonikaDataUpdateCoordinator], SensorEntity
):
    """Teltonika sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TeltonikaDataUpdateCoordinator,
        device_info: DeviceInfo,
        description: SensorEntityDescription,
        modem_id: str,
        modem: ModemStatus,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._modem_id = modem_id
        self._attr_device_info = device_info

        # Create unique ID using entry unique identifier, modem ID, and sensor type
        assert coordinator.config_entry is not None
        entry_unique_id = (
            coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        )
        self._attr_unique_id = f"{entry_unique_id}_{modem_id}_{description.key}"

        # Use translation key for proper naming
        modem_name = getattr(modem, "name", f"Modem {modem_id}")
        self._modem_name = modem_name
        self._attr_translation_key = description.translation_key
        self._attr_translation_placeholders = {"modem_name": modem_name}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._modem_id in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Always set base attributes (all keys must always be present)
        attrs = {
            "modem_id": self._modem_id,
            "modem_name": self._modem_name,
            "connection_type": None,
            "operator": None,
        }

        # Add sensor-specific attributes with None defaults
        if self.entity_description.key in ("rssi", "rsrp", "rsrq", "sinr"):
            attrs.update(
                {
                    "band": None,
                    "state": None,
                }
            )

        if self._modem_id not in self.coordinator.data:
            self._attr_native_value = None
            self._attr_extra_state_attributes = attrs
            super()._handle_coordinator_update()
            return

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

        # Update attributes with modem data
        attrs["modem_name"] = getattr(modem, "name", self._modem_name)
        attrs["connection_type"] = getattr(modem, "conntype", None)
        attrs["operator"] = getattr(modem, "operator", None)

        # Update sensor-specific attributes
        if self.entity_description.key in ("rssi", "rsrp", "rsrq", "sinr"):
            band = getattr(modem, "sc_band_av", None) or getattr(modem, "band", None)
            attrs["band"] = band
            attrs["state"] = getattr(modem, "state", None)

        self._attr_extra_state_attributes = attrs
        super()._handle_coordinator_update()
