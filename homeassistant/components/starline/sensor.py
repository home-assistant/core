"""Reads vehicle status from StarLine API."""
from homeassistant.components.sensor import DEVICE_CLASS_TEMPERATURE, SensorEntity
from homeassistant.const import (
    LENGTH_KILOMETERS,
    PERCENTAGE,
    TEMP_CELSIUS,
    VOLT,
    VOLUME_LITERS,
)
from homeassistant.helpers.icon import icon_for_battery_level, icon_for_signal_level

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

SENSOR_TYPES = {
    "battery": ["Battery", None, VOLT, None],
    "balance": ["Balance", None, None, "mdi:cash-multiple"],
    "ctemp": ["Interior Temperature", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, None],
    "etemp": ["Engine Temperature", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, None],
    "gsm_lvl": ["GSM Signal", None, PERCENTAGE, None],
    "fuel": ["Fuel Volume", None, None, "mdi:fuel"],
    "errors": ["OBD Errors", None, None, "mdi:alert-octagon"],
    "mileage": ["Mileage", None, LENGTH_KILOMETERS, "mdi:counter"],
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine sensors."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in account.api.devices.values():
        for key, value in SENSOR_TYPES.items():
            sensor = StarlineSensor(account, device, key, *value)
            if sensor.state is not None:
                entities.append(sensor)
    async_add_entities(entities)


class StarlineSensor(StarlineEntity, SensorEntity):
    """Representation of a StarLine sensor."""

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        key: str,
        name: str,
        device_class: str,
        unit: str,
        icon: str,
    ):
        """Initialize StarLine sensor."""
        super().__init__(account, device, key, name)
        self._device_class = device_class
        self._unit = unit
        self._icon = icon

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._key == "battery":
            return icon_for_battery_level(
                battery_level=self._device.battery_level_percent,
                charging=self._device.car_state.get("ign", False),
            )
        if self._key == "gsm_lvl":
            return icon_for_signal_level(signal_level=self._device.gsm_level_percent)
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._key == "battery":
            return self._device.battery_level
        if self._key == "balance":
            return self._device.balance.get("value")
        if self._key == "ctemp":
            return self._device.temp_inner
        if self._key == "etemp":
            return self._device.temp_engine
        if self._key == "gsm_lvl":
            return self._device.gsm_level_percent
        if self._key == "fuel" and self._device.fuel:
            return self._device.fuel.get("val")
        if self._key == "errors" and self._device.errors:
            return self._device.errors.get("val")
        if self._key == "mileage" and self._device.mileage:
            return self._device.mileage.get("val")
        return None

    @property
    def unit_of_measurement(self):
        """Get the unit of measurement."""
        if self._key == "balance":
            return self._device.balance.get("currency") or "₽"
        if self._key == "fuel":
            type_value = self._device.fuel.get("type")
            if type_value == "percents":
                return PERCENTAGE
            if type_value == "litres":
                return VOLUME_LITERS
        return self._unit

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._key == "balance":
            return self._account.balance_attrs(self._device)
        if self._key == "gsm_lvl":
            return self._account.gsm_attrs(self._device)
        if self._key == "errors":
            return self._account.errors_attrs(self._device)
        return None
