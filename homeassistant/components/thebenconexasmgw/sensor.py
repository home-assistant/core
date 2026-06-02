"""Sensor for the Theben Conexa Smartmeter gateway integration."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SmgwSensorCoordinator, ThebenConfigEntry
from .entity import ConexaSMGWEntity
from .smgw import ConexaSMGW


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThebenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    sensors = [
        TotalInOutSensor(key, entry.runtime_data.coordinator, entry.runtime_data.api)
        for key in entry.runtime_data.coordinator.data
    ]
    async_add_entities(sensors)


class TotalInOutSensor(ConexaSMGWEntity, SensorEntity):
    """Represents total Meter readings."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_should_poll = False

    def __init__(
        self, key: str, coordinator: SmgwSensorCoordinator, data: ConexaSMGW
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        if "10001080" in key:
            # This is the total power consumed channel, which has the OBIS code 1-0:1.8.0 (or 10001080)
            self._attr_name = "Total Power Consumed"
            self._attr_icon = "mdi:home-import-outline"
        elif "10002080" in key:
            # This is the total power supplied channel, which has the OBIS code 1-0:2.8.0 (or 10002080)
            self._attr_name = "Total Power Supplied"
            self._attr_icon = "mdi:home-export-outline"
        # TODO: How to handle error cases? pylint: disable=fixme

        self.__key = key
        self._attr_native_value = coordinator.data[key].value
        # As far as I know the Conexa 3.0 returns always Wh but there is the possibility that it returns Joules
        if coordinator.data[key].unit.upper() == "J":
            self._attr_native_unit_of_measurement = UnitOfEnergy.JOULE
        self._attr_unique_id = f"{data.gatewayInfo.smgwID}-{key}"
        # TODO: Where to put the Device Info?
        self._attr_device_info = DeviceInfo(
            name=data.gatewayInfo.smgwID,
            identifiers={(DOMAIN, data.gatewayInfo.smgwID)},
            manufacturer="Theben AG",
            model="CONEXA 3.0 Smart Meter Gateway",
            sw_version=data.gatewayInfo.firmwareVersion,
            serial_number=data.gatewayInfo.smgwID,
            # configuration_url=f"https://{data.host}", TODO: Should I add it? Is it useful?
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data[self.__key].value
        self.async_write_ha_state()
