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
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_RESOURCE
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FroniusSolarNet
from .const import DOMAIN
from .coordinator import (
    FroniusInverterUpdateCoordinator,
    FroniusLoggerUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
    _FroniusUpdateCoordinator,
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
    _LOGGER.warning(
        "Loading Fronius via platform setup is deprecated. Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fronius sensor entities based on a config entry."""
    solar_net: FroniusSolarNet = hass.data[DOMAIN][config_entry.entry_id]
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

    def __init__(
        self,
        coordinator: _FroniusUpdateCoordinator,
        entity_description: SensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.solar_net_id = solar_net_id

    @property
    def _device_data(self) -> dict[str, Any]:
        return self.coordinator.data[self.solar_net_id]  # type: ignore[no-any-return]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_native_value = self._device_data[self.entity_description.key][
                "value"
            ]
        except KeyError:
            return
        self.async_write_ha_state()


class InverterSensor(_FroniusSensorEntity):
    """Defines a Fronius inverter device sensor entity."""

    coordinator: FroniusInverterUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius inverter sensor."""
        super().__init__(*args, **kwargs)
        # device_info created in __init__ from a `GetInverterInfo` request
        self._attr_device_info = self.coordinator.inverter_info.device_info
        self._attr_native_value = self._device_data[self.entity_description.key][
            "value"
        ]
        self._attr_unique_id = (
            f"{self.coordinator.inverter_info.unique_id}-{self.entity_description.key}"
        )


class LoggerSensor(_FroniusSensorEntity):
    """Defines a Fronius logger device sensor entity."""

    coordinator: FroniusLoggerUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(*args, **kwargs)
        logger_data = self._device_data
        # Logger device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.solar_net_device_id)}
        )
        self._attr_native_unit_of_measurement = logger_data[
            self.entity_description.key
        ].get("unit")
        self._attr_native_value = logger_data[self.entity_description.key]["value"]
        self._attr_unique_id = (
            f'{logger_data["unique_identifier"]["value"]}-{self.entity_description.key}'
        )


class MeterSensor(_FroniusSensorEntity):
    """Defines a Fronius meter device sensor entity."""

    coordinator: FroniusMeterUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius meter sensor."""
        super().__init__(*args, **kwargs)
        meter_data = self._device_data

        self._attr_extra_state_attributes = {
            "meter_loaction": meter_data["meter_location"]["value"],
            "enable": meter_data["enable"]["value"],
            "visible": meter_data["visible"]["value"],
        }
        self._attr_device_info = DeviceInfo(
            name=meter_data["model"]["value"],
            identifiers={(DOMAIN, meter_data["serial"]["value"])},
            manufacturer=meter_data["manufacturer"]["value"],
            model=meter_data["model"]["value"],
            via_device=(DOMAIN, self.coordinator.solar_net_device_id),
        )
        self._attr_native_value = meter_data[self.entity_description.key]["value"]
        self._attr_unique_id = (
            f'{meter_data["serial"]["value"]}-{self.entity_description.key}'
        )


class PowerFlowSensor(_FroniusSensorEntity):
    """Defines a Fronius power flow sensor entity."""

    coordinator: FroniusPowerFlowUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius power flow sensor."""
        super().__init__(*args, **kwargs)
        # device_info created in __init__ from a `GetLoggerInfo` or `GetInverterInfo` request
        self._attr_device_info = self.coordinator.power_flow_info.device_info
        self._attr_native_value = self._device_data[self.entity_description.key][
            "value"
        ]
        self._attr_unique_id = (
            f"{self.coordinator.power_flow_info.unique_id}"
            f"-power_flow-{self.entity_description.key}"
        )


class StorageSensor(_FroniusSensorEntity):
    """Defines a Fronius storage device sensor entity."""

    coordinator: FroniusStorageUpdateCoordinator

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up an individual Fronius storage sensor."""
        super().__init__(*args, **kwargs)
        storage_data = self._device_data

        self._attr_device_info = DeviceInfo(
            name=storage_data["model"]["value"],
            identifiers={(DOMAIN, storage_data["serial"]["value"])},
            manufacturer=storage_data["manufacturer"]["value"],
            model=storage_data["model"]["value"],
            via_device=(DOMAIN, self.coordinator.solar_net_device_id),
        )
        self._attr_native_value = storage_data[self.entity_description.key]["value"]
        self._attr_unique_id = (
            f'{storage_data["serial"]["value"]}-{self.entity_description.key}'
        )
