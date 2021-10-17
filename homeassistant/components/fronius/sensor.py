"""Support for Fronius devices."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_RESOURCE
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FroniusSolarNet
from .const import DOMAIN
from .coordinator import (
    FroniusCoordinatorBase,
    FroniusInverterUpdateCoordinator,
    FroniusLoggerUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_RESOURCE): cv.url},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: None = None,
) -> None:
    """Import Fronius configuration from yaml."""
    host = config[CONF_RESOURCE]
    solar_net = FroniusSolarNet(hass, host)
    await solar_net.init_devices()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][host] = solar_net

    for inverter_coordinator in solar_net.inverter_coordinators:
        inverter_coordinator.add_entities_for_seen_keys(
            async_add_entities, InverterSensor
        )
    if solar_net.logger_coordinator is not None:
        solar_net.logger_coordinator.add_entities_for_seen_keys(
            async_add_entities, LoggerSensor
        )
    if solar_net.meter_coordinator is not None:
        solar_net.meter_coordinator.add_entities_for_seen_keys(
            async_add_entities, MeterSensor
        )
    if solar_net.power_flow_coordinator is not None:
        solar_net.power_flow_coordinator.add_entities_for_seen_keys(
            async_add_entities, PowerFlowSensor
        )
    if solar_net.storage_coordinator is not None:
        solar_net.storage_coordinator.add_entities_for_seen_keys(
            async_add_entities, StorageSensor
        )


class _FroniusSensorEntity(CoordinatorEntity, SensorEntity):
    """Defines a Fronius coordinator entity."""

    coordinator: FroniusCoordinatorBase

    def __init__(
        self,
        coordinator: FroniusCoordinatorBase,
        entity_description: SensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.solar_net_id = solar_net_id
        self._attr_native_value = self._get_entity_value()

    def _device_data(self) -> dict[str, Any]:
        """Extract information for SolarNet device from coordinator data."""
        return self.coordinator.data[self.solar_net_id]

    def _get_entity_value(self) -> Any:
        """Extract entity value from coordinator. Raises KeyError if not included in latest update."""
        new_value = self.coordinator.data[self.solar_net_id][
            self.entity_description.key
        ]["value"]
        return round(new_value, 4) if isinstance(new_value, float) else new_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self._get_entity_value()
        except KeyError:
            return
        self.async_write_ha_state()


class InverterSensor(_FroniusSensorEntity):
    """Defines a Fronius inverter device sensor entity."""

    coordinator: FroniusInverterUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius inverter sensor."""
        super().__init__(*args, **kwargs)
        self._attr_name = (
            f"Fronius Inverter {self.solar_net_id} - {self.entity_description.name}"
        )
        self._attr_unique_id = (
            f"{self.coordinator.inverter_info.unique_id}-{self.entity_description.key}"
        )


class LoggerSensor(_FroniusSensorEntity):
    """Defines a Fronius logger device sensor entity."""

    coordinator: FroniusLoggerUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(*args, **kwargs)
        logger_data = self._device_data()
        self._attr_name = f"Fronius Logger - {self.entity_description.name}"
        self._attr_native_unit_of_measurement = logger_data[
            self.entity_description.key
        ].get("unit")
        self._attr_unique_id = (
            f'{logger_data["unique_identifier"]["value"]}-{self.entity_description.key}'
        )


class MeterSensor(_FroniusSensorEntity):
    """Defines a Fronius meter device sensor entity."""

    coordinator: FroniusMeterUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(*args, **kwargs)
        meter_data = self._device_data()

        self._attr_extra_state_attributes = {
            "meter_location": meter_data["meter_location"]["value"],
            "enable": meter_data["enable"]["value"],
            "visible": meter_data["visible"]["value"],
        }
        self._attr_name = (
            f"Fronius Meter {self.solar_net_id} - {self.entity_description.name}"
        )
        self._attr_unique_id = (
            f'{meter_data["serial"]["value"]}-{self.entity_description.key}'
        )


class PowerFlowSensor(_FroniusSensorEntity):
    """Defines a Fronius power flow sensor entity."""

    coordinator: FroniusPowerFlowUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius power flow sensor."""
        super().__init__(*args, **kwargs)
        self._attr_name = f"Fronius power flow - {self.entity_description.name}"
        self._attr_unique_id = (
            f"{self.coordinator.solar_net.solar_net_device_id}"
            f"-power_flow-{self.entity_description.key}"
        )


class StorageSensor(_FroniusSensorEntity):
    """Defines a Fronius storage device sensor entity."""

    coordinator: FroniusStorageUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius storage sensor."""
        super().__init__(*args, **kwargs)
        storage_data = self._device_data()

        self._attr_name = (
            f"Fronius Storage {self.solar_net_id} - {self.entity_description.name}"
        )
        self._attr_unique_id = (
            f'{storage_data["serial"]["value"]}-{self.entity_description.key}'
        )
