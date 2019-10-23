"""Reads vehicle status from StarLine API."""
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level, icon_for_signal_level
from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

SENSOR_TYPES = {
    "battery": ["Battery", "V", "mdi:battery"],
    "balance": ["Balance", "$", "mdi:cash-multiple"],
    "ctemp": ["Interior Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "etemp": ["Engine Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "gsm_lvl": ["GSM Signal", "%", "mdi:signal"],
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine sensors."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in account.api.devices.values():
        for key, value in SENSOR_TYPES.items():
            entities.append(StarlineSensor(account, device, key, *value))
    async_add_entities(entities)
    return True


class StarlineSensor(StarlineEntity, Entity):
    """Representation of a StarLine sensor."""

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        key: str,
        name: str,
        unit: str,
        icon: str,
    ):
        """Constructor."""
        super().__init__(account, device, key, name)
        self._unit = unit
        self._icon = icon

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._key == "battery":
            return icon_for_battery_level(
                battery_level=self._device.battery_level_percent,
                charging=self._device.car_state["ign"],
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
            return self._device.balance["value"]
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
            return self._device.balance["currency"]
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._key == "balance":
            return self._account.balance_attrs(self._device)
        if self._key == "gsm_lvl":
            return self._account.gsm_attrs(self._device)
        return None
