"""Support for power sensors in WeMo Insight devices."""
import asyncio

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import StateType
from homeassistant.util import convert

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoEntity
from .wemo_device import DeviceCoordinator


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WeMo sensors."""

    async def _discovered_wemo(coordinator: DeviceCoordinator):
        """Handle a discovered Wemo device."""
        async_add_entities(
            [InsightCurrentPower(coordinator), InsightTodayEnergy(coordinator)]
        )

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.sensor", _discovered_wemo)

    await asyncio.gather(
        *(
            _discovered_wemo(coordinator)
            for coordinator in hass.data[WEMO_DOMAIN]["pending"].pop("sensor")
        )
    )


class InsightSensor(WemoEntity, SensorEntity):
    """Common base for WeMo Insight power sensors."""

    @property
    def name_suffix(self) -> str:
        """Return the name of the entity if any."""
        return self.entity_description.name

    @property
    def unique_id_suffix(self) -> str:
        """Return the id of this entity."""
        return self.entity_description.key

    @property
    def available(self) -> str:
        """Return true if sensor is available."""
        return (
            self.entity_description.key in self.wemo.insight_params
            and super().available
        )


class InsightCurrentPower(InsightSensor):
    """Current instantaineous power consumption."""

    entity_description = SensorEntityDescription(
        key="currentpower",
        name="Current Power",
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=POWER_WATT,
    )

    @property
    def native_value(self) -> StateType:
        """Return the current power consumption."""
        return (
            convert(
                self.wemo.insight_params.get(self.entity_description.key), float, 0.0
            )
            / 1000.0
        )


class InsightTodayEnergy(InsightSensor):
    """Energy used today."""

    entity_description = SensorEntityDescription(
        key="todaymw",
        name="Today Energy",
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
    )

    @property
    def native_value(self) -> StateType:
        """Return the current energy use today."""
        miliwatts = convert(
            self.wemo.insight_params.get(self.entity_description.key), float, 0.0
        )
        return round(miliwatts / (1000.0 * 1000.0 * 60), 2)
