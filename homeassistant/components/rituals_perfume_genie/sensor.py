"""Support for Rituals Perfume Genie sensors."""
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
)

from .const import COORDINATORS, DEVICES, DOMAIN, HUB
from .entity import SENSORS, DiffuserEntity

ID = "id"
TITLE = "title"
ICON = "icon"
WIFI = "wific"
BATTERY = "battc"
PERFUME = "rfidc"
FILL = "fillc"

BATTERY_CHARGING_ID = 21
PERFUME_NO_CARTRIDGE_ID = 19
FILL_NO_CARTRIDGE_ID = 12

BATTERY_SUFFIX = " Battery"
PERFUME_SUFFIX = " Perfume"
FILL_SUFFIX = " Fill"
WIFI_SUFFIX = " Wifi"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the diffuser sensors."""
    diffusers = hass.data[DOMAIN][config_entry.entry_id][DEVICES]
    coordinators = hass.data[DOMAIN][config_entry.entry_id][COORDINATORS]
    entities = []
    for hublot, diffuser in diffusers.items():
        coordinator = coordinators[hublot]
        entities.append(DiffuserPerfumeSensor(diffuser, coordinator))
        entities.append(DiffuserFillSensor(diffuser, coordinator))
        entities.append(DiffuserWifiSensor(diffuser, coordinator))
        if BATTERY in diffuser.data[HUB][SENSORS]:
            entities.append(DiffuserBatterySensor(diffuser, coordinator))

    async_add_entities(entities)


class DiffuserPerfumeSensor(DiffuserEntity):
    """Representation of a diffuser perfume sensor."""

    def __init__(self, diffuser, coordinator):
        """Initialize the perfume sensor."""
        super().__init__(diffuser, coordinator, PERFUME_SUFFIX)

    @property
    def icon(self):
        """Return the perfume sensor icon."""
        if self.coordinator.data[HUB][SENSORS][PERFUME][ID] == PERFUME_NO_CARTRIDGE_ID:
            return "mdi:tag-remove"
        return "mdi:tag-text"

    @property
    def state(self):
        """Return the state of the perfume sensor."""
        return self.coordinator.data[HUB][SENSORS][PERFUME][TITLE]


class DiffuserFillSensor(DiffuserEntity):
    """Representation of a diffuser fill sensor."""

    def __init__(self, diffuser, coordinator):
        """Initialize the fill sensor."""
        super().__init__(diffuser, coordinator, FILL_SUFFIX)

    @property
    def icon(self):
        """Return the fill sensor icon."""
        if self.coordinator.data[HUB][SENSORS][FILL][ID] == FILL_NO_CARTRIDGE_ID:
            return "mdi:beaker-question"
        return "mdi:beaker"

    @property
    def state(self):
        """Return the state of the fill sensor."""
        return self.coordinator.data[HUB][SENSORS][FILL][TITLE]


class DiffuserBatterySensor(DiffuserEntity):
    """Representation of a diffuser battery sensor."""

    def __init__(self, diffuser, coordinator):
        """Initialize the battery sensor."""
        super().__init__(diffuser, coordinator, BATTERY_SUFFIX)

    @property
    def icon(self):
        """Return the battery sensor icon."""
        return {
            "battery-charge.png": "mdi:battery-charging",
            "battery-full.png": "mdi:battery",
            "battery-75.png": "mdi:battery-50",
            "battery-50.png": "mdi:battery-20",
            "battery-low.png": "mdi:battery-alert",
        }[self.coordinator.data[HUB][SENSORS][BATTERY][ICON]]

    @property
    def state(self):
        """Return the state of the battery sensor."""
        return self.coordinator.data[HUB][SENSORS][BATTERY][TITLE]

    @property
    def device_class(self):
        """Return the class of the battery sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def device_state_attributes(self):
        """Return the battery state attributes."""
        return {
            ATTR_BATTERY_CHARGING: self.coordinator.data[HUB][SENSORS][BATTERY][ID]
            == BATTERY_CHARGING_ID
        }


class DiffuserWifiSensor(DiffuserEntity):
    """Representation of a diffuser wifi sensor."""

    def __init__(self, diffuser, coordinator):
        """Initialize the wifi sensor."""
        super().__init__(diffuser, coordinator, WIFI_SUFFIX)

    @property
    def icon(self):
        """Return the wifi sensor icon."""
        return {
            "icon-signal.png": "mdi:wifi-strength-4",
            "icon-signal-75.png": "mdi:wifi-strength-3",
            "icon-signal-low.png": "mdi:wifi-strength-1",
            "icon-signal-0.png": "mdi:wifi-strength-outline",
        }[self.coordinator.data[HUB][SENSORS][WIFI][ICON]]

    @property
    def state(self):
        """Return the state of the wifi sensor."""
        return self.coordinator.data[HUB][SENSORS][WIFI][TITLE]

    @property
    def device_class(self):
        """Return the class of the wifi sensor."""
        return DEVICE_CLASS_SIGNAL_STRENGTH
