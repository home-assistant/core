"""Support for Motion Blinds sensors."""
from motionblinds import DEVICE_TYPES_WIFI, BlindType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_AVAILABLE, DOMAIN, KEY_COORDINATOR, KEY_GATEWAY
from .gateway import device_name

ATTR_BATTERY_VOLTAGE = "battery_voltage"
TYPE_BLIND = "blind"
TYPE_GATEWAY = "gateway"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Motion Blinds."""
    entities: list[SensorEntity] = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        entities.append(MotionSignalStrengthSensor(coordinator, blind, TYPE_BLIND))
        if blind.type == BlindType.TopDownBottomUp:
            entities.append(MotionTDBUBatterySensor(coordinator, blind, "Bottom"))
            entities.append(MotionTDBUBatterySensor(coordinator, blind, "Top"))
        elif blind.battery_voltage is not None and blind.battery_voltage > 0:
            # Only add battery powered blinds
            entities.append(MotionBatterySensor(coordinator, blind))

    # Do not add signal sensor twice for direct WiFi blinds
    if motion_gateway.device_type not in DEVICE_TYPES_WIFI:
        entities.append(
            MotionSignalStrengthSensor(coordinator, motion_gateway, TYPE_GATEWAY)
        )

    async_add_entities(entities)


class MotionBatterySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Motion Battery Sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, blind):
        """Initialize the Motion Battery Sensor."""
        super().__init__(coordinator)

        self._blind = blind
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, blind.mac)})
        self._attr_name = f"{device_name(blind)} battery"
        self._attr_unique_id = f"{blind.mac}-battery"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.coordinator.data is None:
            return False

        if not self.coordinator.data[KEY_GATEWAY][ATTR_AVAILABLE]:
            return False

        return self.coordinator.data[self._blind.mac][ATTR_AVAILABLE]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._blind.battery_level

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {ATTR_BATTERY_VOLTAGE: self._blind.battery_voltage}

    async def async_added_to_hass(self) -> None:
        """Subscribe to multicast pushes."""
        self._blind.Register_callback(self.unique_id, self.schedule_update_ha_state)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""
        self._blind.Remove_callback(self.unique_id)
        await super().async_will_remove_from_hass()


class MotionTDBUBatterySensor(MotionBatterySensor):
    """Representation of a Motion Battery Sensor for a Top Down Bottom Up blind."""

    def __init__(self, coordinator, blind, motor):
        """Initialize the Motion Battery Sensor."""
        super().__init__(coordinator, blind)

        self._motor = motor
        self._attr_unique_id = f"{blind.mac}-{motor}-battery"
        self._attr_name = f"{device_name(blind)} {motor} battery"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._blind.battery_level is None:
            return None
        return self._blind.battery_level[self._motor[0]]

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if self._blind.battery_voltage is not None:
            attributes[ATTR_BATTERY_VOLTAGE] = self._blind.battery_voltage[
                self._motor[0]
            ]
        return attributes


class MotionSignalStrengthSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Motion Signal Strength Sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device, device_type):
        """Initialize the Motion Signal Strength Sensor."""
        super().__init__(coordinator)

        if device_type == TYPE_GATEWAY:
            name = "Motion gateway signal strength"
        else:
            name = f"{device_name(device)} signal strength"

        self._device = device
        self._device_type = device_type
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device.mac)})
        self._attr_unique_id = f"{device.mac}-RSSI"
        self._attr_name = name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.coordinator.data is None:
            return False

        gateway_available = self.coordinator.data[KEY_GATEWAY][ATTR_AVAILABLE]
        if self._device_type == TYPE_GATEWAY:
            return gateway_available

        return (
            gateway_available
            and self.coordinator.data[self._device.mac][ATTR_AVAILABLE]
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._device.RSSI

    async def async_added_to_hass(self) -> None:
        """Subscribe to multicast pushes."""
        self._device.Register_callback(self.unique_id, self.schedule_update_ha_state)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe when removed."""
        self._device.Remove_callback(self.unique_id)
        await super().async_will_remove_from_hass()
