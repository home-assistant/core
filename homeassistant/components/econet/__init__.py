"""Support for EcoNet products."""
import asyncio
from datetime import timedelta
import logging

from pyeconet import EcoNetApiInterface
from pyeconet.equipments import EquipmentType
from pyeconet.errors import InvalidCredentialsError, PyeconetError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, TEMP_FAHRENHEIT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import API_CLIENT, DOMAIN, EQUIPMENT

_LOGGER = logging.getLogger(__name__)

ATTR_ON_VACATION = "on_vacation"
ATTR_IN_USE = "in_use"
ATTR_WIFI_SIGNAL = "wifi_signal_strength"
ATTR_ALERT_COUNT = "alert_count"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

INTERVAL = timedelta(minutes=60)


async def async_setup(hass, config):
    """Set up the EcoNet component."""

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][API_CLIENT] = {}
    hass.data[DOMAIN][EQUIPMENT] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    _LOGGER.error(conf)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: conf[CONF_USERNAME],
                CONF_PASSWORD: conf[CONF_PASSWORD],
            },
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up EcoNet as config entry."""
    entry_updates = {}
    if not config_entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = config_entry.data[CONF_USERNAME]
    if entry_updates:
        hass.config_entries.async_update_entry(config_entry, **entry_updates)

    email = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)

    try:
        api = await EcoNetApiInterface.login(email, password=password)
    except InvalidCredentialsError:
        _LOGGER.error("Invalid credentials provided")
        return False
    except PyeconetError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady

    equipment = await api.get_equipment_by_type(
        [EquipmentType.WATER_HEATER, EquipmentType.THERMOSTAT]
    )
    hass.data[DOMAIN][API_CLIENT][config_entry.entry_id] = api
    hass.data[DOMAIN][EQUIPMENT][config_entry.entry_id] = equipment

    for component in ["water_heater", "climate"]:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    api.subscribe()

    async def resubscribe(now):
        """Resubscribe to the MQTT updates."""
        api.unsubscribe()
        api.subscribe()

    async def fetch_update(now):
        """Fetch the latest changes from the API."""
        api.refresh_equipment()

    async_track_time_interval(hass, resubscribe, INTERVAL)
    async_track_time_interval(hass, fetch_update, INTERVAL + timedelta(minutes=1))

    return True


async def async_unload_entry(hass, entry):
    """Unload a EcoNet config entry."""
    tasks = [
        hass.config_entries.async_forward_entry_unload(entry, component)
        for component in ["water_heater", "climate"]
    ]

    await asyncio.gather(*tasks)

    hass.data[DOMAIN][API_CLIENT].pop(entry.entry_id)

    return True


class EcoNetEntity(Entity):
    """Define a base EcoNet entity."""

    def __init__(self, econet):
        """Initialize."""
        self._econet = econet
        self._econet.set_update_callback(self.on_update_received)

    def on_update_received(self):
        """Update the entities when an MQTT message is received in pyeconet."""
        self.schedule_update_ha_state()

    @property
    def available(self):
        """Return if the the device is online or not."""
        return self._econet.connected

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._econet.device_id)},
            "manufacturer": "Rheem",
            "name": self._econet.device_name,
        }

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._econet.away

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        _attr = {
            ATTR_ON_VACATION: self._econet.vacation,
            ATTR_IN_USE: self._econet.running,
        }
        if self._econet.wifi_signal is not None:
            _attr[ATTR_WIFI_SIGNAL] = self._econet.wifi_signal
        _attr[ATTR_ALERT_COUNT] = self._econet.alert_count
        return _attr

    @property
    def name(self):
        """Return the name of the entity."""
        return self._econet.device_name

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._econet.device_id

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False
