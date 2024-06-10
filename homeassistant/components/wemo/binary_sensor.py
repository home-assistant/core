"""Support for WeMo binary sensors."""

from pywemo import Insight, Maker, StandbyState

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import async_wemo_dispatcher_connect
from .coordinator import DeviceCoordinator
from .entity import WemoBinaryStateEntity, WemoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    _config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeMo binary sensors."""

    async def _discovered_wemo(coordinator: DeviceCoordinator) -> None:
        """Handle a discovered Wemo device."""
        if isinstance(coordinator.wemo, Insight):
            async_add_entities([InsightBinarySensor(coordinator)])
        elif isinstance(coordinator.wemo, Maker):
            async_add_entities([MakerBinarySensor(coordinator)])
        else:
            async_add_entities([WemoBinarySensor(coordinator)])

    await async_wemo_dispatcher_connect(hass, _discovered_wemo)


class WemoBinarySensor(WemoBinaryStateEntity, BinarySensorEntity):
    """Representation a WeMo binary sensor."""


class MakerBinarySensor(WemoEntity, BinarySensorEntity):
    """Maker device's sensor port."""

    _name_suffix = "Sensor"
    wemo: Maker

    @property
    def is_on(self) -> bool:
        """Return true if the Maker's sensor is pulled low."""
        return self.wemo.has_sensor != 0 and self.wemo.sensor_state == 0


class InsightBinarySensor(WemoBinarySensor):
    """Sensor representing the device connected to the Insight Switch."""

    _name_suffix = "Device"
    wemo: Insight

    @property
    def is_on(self) -> bool:
        """Return true device connected to the Insight Switch is on."""
        return super().is_on and self.wemo.standby_state == StandbyState.ON
