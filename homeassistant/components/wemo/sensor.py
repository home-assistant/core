"""Support for power sensors in WeMo Insight devices."""
import asyncio
from datetime import datetime, timedelta
from typing import Callable

from homeassistant import util
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import StateType
from homeassistant.util import convert, dt

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoSubscriptionEntity
from .wemo_device import DeviceWrapper

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WeMo sensors."""

    async def _discovered_wemo(device: DeviceWrapper):
        """Handle a discovered Wemo device."""

        @util.Throttle(SCAN_INTERVAL)
        def update_insight_params():
            device.wemo.update_insight_params()

        async_add_entities(
            [
                InsightCurrentPower(device, update_insight_params),
                InsightTodayEnergy(device, update_insight_params),
            ]
        )

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.sensor", _discovered_wemo)

    await asyncio.gather(
        *(
            _discovered_wemo(device)
            for device in hass.data[WEMO_DOMAIN]["pending"].pop("sensor")
        )
    )


class InsightSensor(WemoSubscriptionEntity, SensorEntity):
    """Common base for WeMo Insight power sensors."""

    def __init__(
        self,
        device: DeviceWrapper,
        update_insight_params: Callable,
        name_suffix: str,
        device_class: str,
        unit_of_measurement: str,
    ) -> None:
        """Initialize the WeMo Insight power sensor."""
        super().__init__(device)
        self._update_insight_params = update_insight_params
        self._name_suffix = name_suffix
        self._attr_device_class = device_class
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_unit_of_measurement = unit_of_measurement

    @property
    def name(self) -> str:
        """Return the name of the entity if any."""
        return f"{self.wemo.name} {self._name_suffix}"

    @property
    def unique_id(self) -> str:
        """Return the id of this entity."""
        return f"{self.wemo.serialnumber}_{self._name_suffix}"

    def _update(self, force_update=True) -> None:
        with self._wemo_exception_handler("update status"):
            if force_update or not self.wemo.insight_params:
                self._update_insight_params()


class InsightCurrentPower(InsightSensor):
    """Current instantaineous power consumption."""

    def __init__(self, device: DeviceWrapper, update_insight_params: Callable) -> None:
        """Initialize the WeMo Insight power sensor."""
        super().__init__(
            device,
            update_insight_params,
            "Current Power",
            DEVICE_CLASS_POWER,
            POWER_WATT,
        )

    @property
    def state(self) -> StateType:
        """Return the current power consumption."""
        if "currentpower" not in self.wemo.insight_params:
            return STATE_UNAVAILABLE
        return convert(self.wemo.insight_params["currentpower"], float, 0.0) / 1000.0


class InsightTodayEnergy(InsightSensor):
    """Energy used today."""

    def __init__(self, device: DeviceWrapper, update_insight_params: Callable) -> None:
        """Initialize the WeMo Insight power sensor."""
        super().__init__(
            device,
            update_insight_params,
            "Today Energy",
            DEVICE_CLASS_ENERGY,
            ENERGY_KILO_WATT_HOUR,
        )

    @property
    def last_reset(self) -> datetime:
        """Return the time when the sensor was initialized."""
        return dt.start_of_local_day()

    @property
    def state(self) -> StateType:
        """Return the current energy use today."""
        if "todaymw" not in self.wemo.insight_params:
            return STATE_UNAVAILABLE
        miliwatts = convert(self.wemo.insight_params["todaymw"], float, 0.0)
        return round(miliwatts / (1000.0 * 1000.0 * 60), 2)
