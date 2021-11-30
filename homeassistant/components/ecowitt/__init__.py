"""The Ecowitt Weather Station Component."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import time

from pyecowitt import WINDCHILL_HYBRID, WINDCHILL_NEW, WINDCHILL_OLD, EcoWittListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PORT,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    CONF_UNIT_BARO,
    CONF_UNIT_LIGHTNING,
    CONF_UNIT_RAIN,
    CONF_UNIT_WIND,
    CONF_UNIT_WINDCHILL,
    DATA_MODEL,
    DATA_PASSKEY,
    DATA_STATIONTYPE,
    DOMAIN,
    PLATFORMS,
    SIGNAL_NEW_SENSOR,
    SIGNAL_REMOVE_ENTITIES,
    SIGNAL_UPDATE,
    W_TYPE_HYBRID,
    W_TYPE_NEW,
    W_TYPE_OLD,
)

NOTIFICATION_ID = DOMAIN
NOTIFICATION_TITLE = "Ecowitt config migrated"

_LOGGER = logging.getLogger(__name__)


@dataclass
class EcowittData:
    """Internal data class for the ecowitt integration."""

    client: type[EcoWittListener]
    registered_devices: list[str]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Ecowitt component from UI."""

    if not entry.options:
        options = {
            CONF_UNIT_BARO: CONF_UNIT_SYSTEM_METRIC,
            CONF_UNIT_WIND: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_UNIT_RAIN: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_UNIT_LIGHTNING: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_UNIT_WINDCHILL: W_TYPE_HYBRID,
        }
        hass.config_entries.async_update_entry(entry, options=options)

    # setup the base connection
    data = EcowittData(EcoWittListener(port=entry.data[CONF_PORT]), [])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data

    if entry.options[CONF_UNIT_WINDCHILL] == W_TYPE_OLD:
        data.client.set_windchill(WINDCHILL_OLD)
    if entry.options[CONF_UNIT_WINDCHILL] == W_TYPE_NEW:
        data.client.set_windchill(WINDCHILL_NEW)
    if entry.options[CONF_UNIT_WINDCHILL] == W_TYPE_HYBRID:
        data.client.set_windchill(WINDCHILL_HYBRID)

    hass.loop.create_task(data.client.listen())
    await data.client.wait_for_valid_data()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    def _new_sensor_callback():
        """Prepare callback for a new sensor addition."""
        _LOGGER.debug("New sensor callback triggered")
        for platform in PLATFORMS:
            async_dispatcher_send(
                hass, SIGNAL_NEW_SENSOR.format(platform, entry.entry_id)
            )

    # set the callback so we know we have new sensors
    data.client.new_sensor_cb = _new_sensor_callback

    async def _async_ecowitt_update_cb(weather_data):
        """Primary update callback called from pyecowitt."""
        _LOGGER.debug("Primary update callback triggered")
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(entry.entry_id))

    # this is part of the base async_setup_entry
    data.client.register_listener(_async_ecowitt_update_cb)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    await data.client.stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("called update listener")
    for platform in PLATFORMS:
        async_dispatcher_send(
            hass, SIGNAL_REMOVE_ENTITIES.format(platform, entry.entry_id)
        )
        async_dispatcher_send(hass, SIGNAL_NEW_SENSOR.format(platform, entry.entry_id))


class EcowittEntity(Entity):
    """Base class for Ecowitt Weather Station."""

    _attr_should_poll = False

    def __init__(self, hass, entry, device):
        """Construct the entity."""
        self.hass = hass
        self.device = device
        self.data = hass.data[DOMAIN][entry.entry_id]
        self._entry = entry
        self._key = device.get_key()
        self._model = self.data.client.get_sensor_value_by_key(DATA_MODEL)
        self._attr_unique_id = f"{self.data.client.get_sensor_value_by_key(DATA_PASSKEY)}-{self.device.get_key()}"
        # remove the _VERSION part of the model
        self._attr_name = f'{self._model.split("_")[0]} {self.device.get_name()}'
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.data.client.get_sensor_value_by_key(DATA_PASSKEY))
            },
            name=self._model,
            manufacturer="Ecowitt",
            model=self._model,
            sw_version=self.data.client.get_sensor_value_by_key(DATA_STATIONTYPE),
            via_device=(
                DOMAIN,
                self.data.client.get_sensor_value_by_key(DATA_STATIONTYPE),
            ),
        )

    async def async_added_to_hass(self):
        """Set up a listener for the entity."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(self._entry.entry_id),
                self.async_write_ha_state,
            )
        )

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        if (self.device.get_lastupd_m() + 5 * 60) < time.monotonic():
            return True
        return False
