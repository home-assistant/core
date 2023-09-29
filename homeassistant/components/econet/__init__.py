"""Support for EcoNet products."""
from datetime import timedelta
import logging

from aiohttp.client_exceptions import ClientError
from pyeconet import EcoNetApiInterface
from pyeconet.equipment import EquipmentType
from pyeconet.errors import (
    GenericHTTPError,
    InvalidCredentialsError,
    InvalidResponseFormat,
    PyeconetError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import API_CLIENT, DOMAIN, EQUIPMENT

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]
PUSH_UPDATE = "econet.push_update"

INTERVAL = timedelta(minutes=60)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up EcoNet as config entry."""

    email = config_entry.data[CONF_EMAIL]
    password = config_entry.data[CONF_PASSWORD]

    try:
        api = await EcoNetApiInterface.login(email, password=password)
    except InvalidCredentialsError:
        _LOGGER.error("Invalid credentials provided")
        return False
    except PyeconetError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    try:
        equipment = await api.get_equipment_by_type(
            [EquipmentType.WATER_HEATER, EquipmentType.THERMOSTAT]
        )
    except (ClientError, GenericHTTPError, InvalidResponseFormat) as err:
        raise ConfigEntryNotReady from err
    hass.data.setdefault(DOMAIN, {API_CLIENT: {}, EQUIPMENT: {}})
    hass.data[DOMAIN][API_CLIENT][config_entry.entry_id] = api
    hass.data[DOMAIN][EQUIPMENT][config_entry.entry_id] = equipment

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    api.subscribe()

    def update_published():
        """Handle a push update."""
        dispatcher_send(hass, PUSH_UPDATE)

    for _eqip in equipment[EquipmentType.WATER_HEATER]:
        _eqip.set_update_callback(update_published)

    for _eqip in equipment[EquipmentType.THERMOSTAT]:
        _eqip.set_update_callback(update_published)

    async def resubscribe(now):
        """Resubscribe to the MQTT updates."""
        await hass.async_add_executor_job(api.unsubscribe)
        api.subscribe()

    async def fetch_update(now):
        """Fetch the latest changes from the API."""
        await api.refresh_equipment()

    config_entry.async_on_unload(async_track_time_interval(hass, resubscribe, INTERVAL))
    config_entry.async_on_unload(
        async_track_time_interval(hass, fetch_update, INTERVAL + timedelta(minutes=1))
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a EcoNet config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][API_CLIENT].pop(entry.entry_id)
        hass.data[DOMAIN][EQUIPMENT].pop(entry.entry_id)
    return unload_ok


class EcoNetEntity(Entity):
    """Define a base EcoNet entity."""

    _attr_should_poll = False

    def __init__(self, econet):
        """Initialize."""
        self._econet = econet
        self._attr_name = econet.device_name
        self._attr_unique_id = f"{econet.device_id}_{econet.device_name}"

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, PUSH_UPDATE, self.on_update_received)
        )

    @callback
    def on_update_received(self):
        """Update was pushed from the ecoent API."""
        self.async_write_ha_state()

    @property
    def available(self):
        """Return if the device is online or not."""
        return self._econet.connected

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._econet.device_id)},
            manufacturer="Rheem",
            name=self._econet.device_name,
        )

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.FAHRENHEIT
