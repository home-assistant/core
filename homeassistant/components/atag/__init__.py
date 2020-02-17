"""The ATAG Integration."""
from datetime import timedelta

from pyatag import AtagDataStore, AtagException

from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_ID,
    ATTR_MODE,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    EVENT_HOMEASSISTANT_STOP,
    PRESSURE_BAR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, asyncio, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import dispatcher
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

DOMAIN = "atag"
DATA_LISTENER = "listener"
SIGNAL_UPDATE_ATAG = f"{DOMAIN}_update"
PLATFORMS = [CLIMATE, WATER_HEATER, SENSOR]
SCAN_INTERVAL = timedelta(seconds=30)
HOUR = "h"
FIRE = "fire"
PERCENTAGE = "%"

ICONS = {
    TEMP_CELSIUS: "mdi:thermometer",
    PRESSURE_BAR: "mdi:gauge",
    FIRE: "mdi:fire",
    ATTR_MODE: "mdi:settings",
}

ENTITY_TYPES = {
    SENSOR: {
        1: {
            ATTR_NAME: "Outside Temperature",
            ATTR_ID: "outside_temp",
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            ATTR_ICON: ICONS[TEMP_CELSIUS],
        },
        2: {
            ATTR_NAME: "Average Outside Temperature",
            ATTR_ID: "tout_avg",
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            ATTR_ICON: ICONS[TEMP_CELSIUS],
        },
        3: {
            ATTR_NAME: "Weather Status",
            ATTR_ID: "weather_status",
            ATTR_UNIT_OF_MEASUREMENT: None,
            ATTR_DEVICE_CLASS: None,
            ATTR_ICON: None,
        },
        4: {
            ATTR_NAME: "Operation Mode",
            ATTR_ID: "ch_mode",
            ATTR_UNIT_OF_MEASUREMENT: None,
            ATTR_DEVICE_CLASS: None,
            ATTR_ICON: ICONS[ATTR_MODE],
        },
        5: {
            ATTR_NAME: "CH Water Pressure",
            ATTR_ID: "ch_water_pres",
            ATTR_UNIT_OF_MEASUREMENT: PRESSURE_BAR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
            ATTR_ICON: ICONS[PRESSURE_BAR],
        },
        6: {
            ATTR_NAME: "CH Water Temperature",
            ATTR_ID: "ch_water_temp",
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            ATTR_ICON: ICONS[TEMP_CELSIUS],
        },
        7: {
            ATTR_NAME: "CH Return Temperature",
            ATTR_ID: "ch_return_temp",
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            ATTR_ICON: ICONS[TEMP_CELSIUS],
        },
        8: {
            ATTR_NAME: "Burning Hours",
            ATTR_ID: "burning_hours",
            ATTR_UNIT_OF_MEASUREMENT: HOUR,
            ATTR_DEVICE_CLASS: None,
            ATTR_ICON: ICONS[FIRE],
        },
        9: {
            ATTR_NAME: "Flame",
            ATTR_ID: "rel_mod_level",
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_DEVICE_CLASS: None,
            ATTR_ICON: ICONS[FIRE],
        },
    },
    CLIMATE: {ATTR_NAME: CLIMATE.title()},
    WATER_HEATER: {ATTR_NAME: "Domestic Hot Water"},
}


async def async_setup(hass: HomeAssistant, config):
    """Set up the Atag component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Atag integration from a config entry."""
    session = async_get_clientsession(hass)
    atag = AtagDataStore(session, paired=True, **entry.data)

    try:
        await atag.async_update()
        if not atag.sensordata:
            raise ConfigEntryNotReady
    except AtagException:
        raise ConfigEntryNotReady
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = atag

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    async def refresh(event_time):
        """Poll Atag for latest data."""
        await atag.async_update()
        dispatcher.async_dispatcher_send(hass, SIGNAL_UPDATE_ATAG)

    async def async_close_session(event):
        """Close the session on shutdown."""
        await atag.async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_session)

    hass.data.setdefault(DATA_LISTENER, {})[entry.entry_id] = async_track_time_interval(
        hass, refresh, SCAN_INTERVAL
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload Atag config entry."""
    remove_listener = hass.data[DATA_LISTENER].pop(entry.entry_id)
    remove_listener()
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class AtagEntity(Entity):
    """Defines a base Atag entity."""

    def __init__(self, atag: AtagDataStore, atag_type: dict) -> None:
        """Initialize the Atag entity."""
        self.atag = atag

        self._id = atag_type.get(ATTR_ID)
        self._name = f"{atag_type[ATTR_NAME]}"
        self._icon = atag_type.get(ATTR_ICON)
        self._unit = atag_type.get(ATTR_UNIT_OF_MEASUREMENT)
        self._class = atag_type.get(ATTR_DEVICE_CLASS)
        self._sensor_value = atag.sensordata.get(self._id, {}).get(ATTR_STATE)
        self._unsub_dispatcher = None

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self.atag.device
        host = self.atag.config.host
        version = self.atag.apiversion
        return {
            "identifiers": {(DOMAIN, device, host)},
            ATTR_NAME: "Atag Thermostat",
            "model": "Atag One",
            "sw_version": version,
            "manufacturer": "Atag",
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        if hasattr(self, "_icon"):
            return self._icon

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if hasattr(self, "_unit"):
            return self._unit

    @property
    def device_class(self):
        """Return the device class."""
        if hasattr(self, "_class"):
            return self._class

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self._unsub_dispatcher = dispatcher.async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ATAG, self._update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from update signal."""
        self._unsub_dispatcher()

    @callback
    def _update_callback(self) -> None:
        """Schedule an immediate update of the entity."""
        self.async_schedule_update_ha_state(True)

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self.atag.device}-{self._name}"
