"""Sensors for Savant Home Automation."""

import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    sensors: list[SensorEntity] = []
    coordinator = config.runtime_data
    if config.data["type"] == "Audio":
        sensors = [
            RawVolumeSensor(coordinator, int(output)) for output in coordinator.outputs
        ]
    else:
        sensors = []
    sensors.append(UptimeSensor(coordinator))

    async_add_entities(sensors)
    coordinator.sensors.extend(sensors)


class RawVolumeSensor(CoordinatorEntity, SensorEntity):
    """Volume sensor (diagnostic) for an output of a Savant audio matrix."""

    _attr_device_class = SensorDeviceClass.SOUND_PRESSURE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Volume"
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "dB"

    def __init__(self, coordinator, port):
        """Create a RawVolumeSensor setting the context to the port index."""
        super().__init__(coordinator, context=port)
        self.port = port

    @property
    def unique_id(self):
        """The unique id of the sensor - uses the savantID of the coordinator and the port index."""
        return f"{self.coordinator.info['savantID']}_{self.port}_volume"

    @property
    def device_info(self):
        """Links to the device defined by the media player."""
        return dr.DeviceInfo(
            identifiers={
                (DOMAIN, f"{self.coordinator.info['savantID']}.output{self.port}")
            },
            via_device=(DOMAIN, self.coordinator.info["savantID"]),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data is None:
            self._attr_available = False
        else:
            self._attr_available = True
            port_data = data[self.port]
            self._attr_native_value = int(port_data["other"]["volume"])
        self.async_write_ha_state()


class UptimeSensor(CoordinatorEntity, SensorEntity):
    """Uptime sensor (diagnostic) for the matrix."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_name = "Uptime"
    _attr_should_poll = False

    def __init__(self, coordinator):
        """Create an Uptime setting the value to the timestamp from the coordinators info."""
        super().__init__(coordinator)
        ts = coordinator.info["uptime"]["since"]
        self._attr_native_value = datetime.datetime.fromtimestamp(
            ts, tz=datetime.timezone(datetime.timedelta(hours=0))
        )

    @property
    def unique_id(self):
        """The unique id of the sensor - uses the savantID of the coordinator."""
        return f"{self.coordinator.info['savantID']}_uptime"

    @property
    def device_info(self):
        """Links to the the device for the switch itself, rather than one of the ports."""
        return dr.DeviceInfo(identifiers={(DOMAIN, self.coordinator.info["savantID"])})
