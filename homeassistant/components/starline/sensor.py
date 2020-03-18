"""Reads vehicle status from StarLine API."""
from homeassistant.components.sensor import DEVICE_CLASS_TEMPERATURE
from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level, icon_for_signal_level

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

SENSOR_TYPES = {
    "battery": ["Battery", None, "V", None],
    "balance": ["Balance", None, None, "mdi:cash-multiple"],
    "ctemp": ["Interior Temperature", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, None],
    "etemp": ["Engine Temperature", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, None],
    "gsm_lvl": ["GSM Signal", None, UNIT_PERCENTAGE, None],
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


class StarlineSensor(StarlineEntity, Entity):
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
        return None

    @property
    def unit_of_measurement(self):
        """Get the unit of measurement."""
        if self._key == "balance":
            return self._device.balance.get("currency") or "₽"
        return self._unit

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._key == "balance":
            return self._account.balance_attrs(self._device)
        if self._key == "gsm_lvl":
            return self._account.gsm_attrs(self._device)
        return None
