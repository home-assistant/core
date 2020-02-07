"""The ATAG Integration."""
from datetime import timedelta

from pyatag import SENSOR_TYPES, AtagDataStore, AtagException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
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
SIGNAL_UPDATE_ATAG = "atag_update"
PLATFORMS = ["sensor", "climate", "water_heater"]
SCAN_INTERVAL = timedelta(seconds=30)
UNIT_TO_CLASS = {TEMP_CELSIUS: DEVICE_CLASS_TEMPERATURE, PRESSURE_BAR: DEVICE_CLASS_PRESSURE}


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

    def __init__(self, atag: AtagDataStore, atagtype: str) -> None:
        """Initialize the Atag entity."""
        if atagtype not in SENSOR_TYPES:
            self._type = atagtype
        else:
            sensortype = SENSOR_TYPES[atagtype]
            self._type = sensortype["type"]
            self._unit = sensortype["unit"]
            self._datafield = sensortype["datafield"]
            self._state = atag.sensordata[self._datafield]["state"]
            self._icon = atag.sensordata[self._datafield].get("icon")

        self._name = f"{DOMAIN.title()} {self._type}"
        self.atag = atag
        self._unsub_dispatcher = None

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self.atag.device
        host = self.atag.config.host
        version = self.atag.apiversion
        return {
            "identifiers": {(DOMAIN, device, host)},
            "name": "Atag Thermostat",
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
        if hasattr(self, "_unit"):
            return UNIT_TO_CLASS.get(self._unit)

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
        return f"{DOMAIN.title()}-{self._type}-{self.atag.device}"
