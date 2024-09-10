"""Component providing support for Reolink sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from reolink_aio.api import Host
from reolink_aio.enums import BatteryEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import ReolinkData
from .const import DOMAIN
from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkHostCoordinatorEntity,
    ReolinkHostEntityDescription,
)


@dataclass(frozen=True, kw_only=True)
class ReolinkSensorEntityDescription(
    SensorEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes sensor entities for a camera channel."""

    value: Callable[[Host, int], StateType]


@dataclass(frozen=True, kw_only=True)
class ReolinkHostSensorEntityDescription(
    SensorEntityDescription,
    ReolinkHostEntityDescription,
):
    """A class that describes host sensor entities."""

    value: Callable[[Host], StateType]


SENSORS = (
    ReolinkSensorEntityDescription(
        key="ptz_pan_position",
        cmd_key="GetPtzCurPos",
        translation_key="ptz_pan_position",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda api, ch: api.ptz_pan_position(ch),
        supported=lambda api, ch: api.supported(ch, "ptz_position"),
    ),
    ReolinkSensorEntityDescription(
        key="battery_percent",
        cmd_key="GetBatteryInfo",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda api, ch: api.battery_percentage(ch),
        supported=lambda api, ch: api.supported(ch, "battery"),
    ),
    ReolinkSensorEntityDescription(
        key="battery_temperature",
        cmd_key="GetBatteryInfo",
        translation_key="battery_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda api, ch: api.battery_temperature(ch),
        supported=lambda api, ch: api.supported(ch, "battery"),
    ),
    ReolinkSensorEntityDescription(
        key="battery_state",
        cmd_key="GetBatteryInfo",
        translation_key="battery_state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[state.name for state in BatteryEnum],
        value=lambda api, ch: BatteryEnum(api.battery_status(ch)).name,
        supported=lambda api, ch: api.supported(ch, "battery"),
    ),
)

HOST_SENSORS = (
    ReolinkHostSensorEntityDescription(
        key="wifi_signal",
        cmd_key="GetWifiSignal",
        translation_key="wifi_signal",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda api: api.wifi_signal,
        supported=lambda api: api.supported(None, "wifi") and api.wifi_connection,
    ),
)

HDD_SENSORS = (
    ReolinkSensorEntityDescription(
        key="storage",
        cmd_key="GetHddInfo",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda api, idx: api.hdd_storage(idx),
        supported=lambda api, idx: api.supported(None, "hdd"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Reolink IP Camera."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[
        ReolinkSensorEntity | ReolinkHostSensorEntity | ReolinkHddSensorEntity
    ] = [
        ReolinkSensorEntity(reolink_data, channel, entity_description)
        for entity_description in SENSORS
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        ReolinkHostSensorEntity(reolink_data, entity_description)
        for entity_description in HOST_SENSORS
        if entity_description.supported(reolink_data.host.api)
    )
    entities.extend(
        ReolinkHddSensorEntity(reolink_data, hdd_index, entity_description)
        for entity_description in HDD_SENSORS
        for hdd_index in reolink_data.host.api.hdd_list
        if entity_description.supported(reolink_data.host.api, hdd_index)
    )
    async_add_entities(entities)


class ReolinkSensorEntity(ReolinkChannelCoordinatorEntity, SensorEntity):
    """Base sensor class for Reolink IP camera sensors."""

    entity_description: ReolinkSensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkSensorEntityDescription,
    ) -> None:
        """Initialize Reolink sensor."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel)

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self._host.api, self._channel)


class ReolinkHostSensorEntity(ReolinkHostCoordinatorEntity, SensorEntity):
    """Base sensor class for Reolink host sensors."""

    entity_description: ReolinkHostSensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostSensorEntityDescription,
    ) -> None:
        """Initialize Reolink host sensor."""
        self.entity_description = entity_description
        super().__init__(reolink_data)

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self._host.api)


class ReolinkHddSensorEntity(ReolinkHostCoordinatorEntity, SensorEntity):
    """Base sensor class for Reolink host sensors."""

    entity_description: ReolinkSensorEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        hdd_index: int,
        entity_description: ReolinkSensorEntityDescription,
    ) -> None:
        """Initialize Reolink host sensor."""
        self.entity_description = entity_description
        super().__init__(reolink_data)
        self._hdd_index = hdd_index
        self._attr_translation_placeholders = {"hdd_index": str(hdd_index)}
        self._attr_unique_id = (
            f"{self._host.unique_id}_{hdd_index}_{entity_description.key}"
        )
        if self._host.api.hdd_type(hdd_index) == "HDD":
            self._attr_translation_key = "hdd_storage"
        else:
            self._attr_translation_key = "sd_storage"

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the value reported by the sensor."""
        return self.entity_description.value(self._host.api, self._hdd_index)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._host.api.hdd_available(self._hdd_index) and super().available
