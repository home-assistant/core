"""The Ecowitt Weather Station Component."""
import logging
import time

from dataclasses import dataclass

from pyecowitt import (
    EcoWittListener,
    WINDCHILL_OLD,
    WINDCHILL_NEW,
    WINDCHILL_HYBRID,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_registry import (
    async_get_registry as async_get_entity_registry,
)

from homeassistant.const import (
    CONF_PORT,
    CONF_UNIT_SYSTEM_METRIC,
    CONF_UNIT_SYSTEM_IMPERIAL,
)

from .const import (
    CONF_UNIT_BARO,
    CONF_UNIT_WIND,
    CONF_UNIT_RAIN,
    CONF_UNIT_WINDCHILL,
    CONF_UNIT_LIGHTNING,
    DATA_PASSKEY,
    DATA_STATIONTYPE,
    DATA_MODEL,
    DOMAIN,
    ECOWITT_PLATFORMS,
    W_TYPE_NEW,
    W_TYPE_OLD,
    W_TYPE_HYBRID,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_REMOVE_ENTITIES,
    SIGNAL_UPDATE,
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
        entry.options = {
            CONF_UNIT_BARO: CONF_UNIT_SYSTEM_METRIC,
            CONF_UNIT_WIND: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_UNIT_RAIN: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_UNIT_LIGHTNING: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_UNIT_WINDCHILL: W_TYPE_HYBRID,
        }

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

    hass.config_entries.async_setup_platforms(entry, ECOWITT_PLATFORMS)

    async def close_server(*args):
        """Close the ecowitt server."""
        await data.client.stop()

    async def _async_ecowitt_update_cb(weather_data):
        """Primary update callback called from pyecowitt."""
        _LOGGER.debug("Primary update callback triggered.")
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(entry.entry_id))

    # this is part of the base async_setup_entry
    data.client.register_listener(_async_ecowitt_update_cb)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    await data.client.stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, ECOWITT_PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


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
        self._attr_unique_id = f'{self.data.client.get_sensor_value_by_key(DATA_PASSKEY)}-{self.device.get_key()}'
        self._attr_name = f'{self.device.get_name()}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.data.client.get_sensor_value_by_key(DATA_PASSKEY))},
            name=self.data.client.get_sensor_value_by_key(DATA_MODEL),
            manufacturer="Ecowitt",
            model=self.data.client.get_sensor_value_by_key(DATA_MODEL),
            sw_version=self.data.client.get_sensor_value_by_key(DATA_STATIONTYPE),
            via_device=self.data.client.get_sensor_value_by_key(DATA_STATIONTYPE),
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

    # @callback
    # async def remove_entity(self, discovery_info=None):
    #     """Remove an entity."""

    #     if self._key in discovery_info.keys():

    #         registry = await async_get_entity_registry(self.hass)

    #         entity_id = registry.async_get_entity_id(
    #             discovery_info[self._key], DOMAIN, self.unique_id
    #         )

    #         _LOGGER.debug(
    #             f"Found entity {entity_id} for key {self._key} -> Uniqueid: {self.unique_id}"
    #         )
    #         if entity_id:
    #             registry.async_remove(entity_id)

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        if (self.device.get_lastupd_m() + 5 * 60) < time.monotonic():
            return True
        return False
