"""The ATAG Integration"""
from datetime import timedelta
from pyatag import AtagDataStore, SENSOR_TYPES, AtagException
import voluptuous as vol

from homeassistant.core import callback, asyncio, HomeAssistant
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    device_registry as dr,
    dispatcher,
    config_validation as cv,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_PORT,
    CONF_EMAIL,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    EVENT_HOMEASSISTANT_STOP,
)
from . import config_flow
from .const import (
    DOMAIN,
    SIGNAL_UPDATE_ATAG,
    DATA_LISTENER,
    PROJECT_URL,
    UNIT_TO_CLASS,
    DEFAULT_PORT,
    DEFAULT_SENSORS,
    DEFAULT_SCAN_INTERVAL,
)

PLATFORMS = ["sensor", "climate", "water_heater"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_EMAIL): cv.string,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.positive_int,
                vol.Required(CONF_SENSORS, default=DEFAULT_SENSORS): vol.All(
                    cv.ensure_list, [vol.In(DEFAULT_SENSORS)]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config):
    """Set up the Atag component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if any(conf.get(CONF_HOST) in host for host in config_flow.configured_hosts(hass)):
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

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

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, atag.device, atag.config.host)},
        manufacturer=PROJECT_URL,
        name="Atag",
        model="Atag One",
        sw_version=atag.apiversion,
    )

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    async def refresh(event_time):
        """Poll Atag for latest data"""
        await atag.async_update()
        dispatcher.async_dispatcher_send(hass, SIGNAL_UPDATE_ATAG)

    async def async_close_session(event):
        """Close the session on shutdown."""
        await atag.async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_session)

    hass.data.setdefault(DATA_LISTENER, {})[entry.entry_id] = async_track_time_interval(
        hass, refresh, timedelta(seconds=entry.data[CONF_SCAN_INTERVAL])
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
    # await hass.data[DOMAIN][config_entry.entry_id].async_close()
    return unload_ok


class AtagEntity(Entity):
    """Defines a base Atag entity."""

    def __init__(self, atag: AtagDataStore, atagtype: str) -> None:
        """Initialize the Atag entity."""
        sensortype = SENSOR_TYPES.get(atagtype)
        if sensortype is not None:
            self._type = sensortype[0]
            self._unit = sensortype[1]
            self._icon = sensortype[2]
            self._datafield = sensortype[3]
            data = atag.sensordata.get(self._datafield)
            if isinstance(data, list):
                self._state, self._icon = data
            else:
                self._state = data
        else:
            self._type = atagtype

        self._name = " ".join([DOMAIN.title(), self._type])
        self.atag = atag
        self._unsub_dispatcher = None

    @property
    def device_info(self):
        """Return info for device registry"""
        device = self.atag.device
        host = self.atag.config.host
        version = self.atag.apiversion
        return {
            "identifiers": {(DOMAIN, device, host)},
            "name": "Atag Thermostat",
            "model": "Atag One",
            "sw_version": version,
            "manufacturer": PROJECT_URL,
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
        return "-".join([DOMAIN.title(), self._type, self.atag.device])
