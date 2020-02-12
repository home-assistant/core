"""Support for WLED."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict, Optional, Union

from wled import WLED, WLEDConnectionError, WLEDError

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    DATA_WLED_CLIENT,
    DATA_WLED_TIMER,
    DATA_WLED_UPDATED,
    DOMAIN,
)

SCAN_INTERVAL = timedelta(seconds=10)
WLED_COMPONENTS = (LIGHT_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the WLED components."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WLED from a config entry."""

    # Create WLED instance for this entry
    session = async_get_clientsession(hass)
    wled = WLED(entry.data[CONF_HOST], session=session)

    # Ensure we can connect and talk to it
    try:
        await wled.update()
    except WLEDConnectionError as exception:
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_WLED_CLIENT: wled}

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=wled.device.info.mac_address
        )

    # Set up all platforms for this device/entry.
    for component in WLED_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def interval_update(now: dt_util.dt.datetime = None) -> None:
        """Poll WLED device function, dispatches event after update."""
        try:
            await wled.update()
        except WLEDError:
            _LOGGER.debug("An error occurred while updating WLED", exc_info=True)

        # Even if the update failed, we still send out the event.
        # To allow entities to make themselves unavailable.
        async_dispatcher_send(hass, DATA_WLED_UPDATED, entry.entry_id)

    # Schedule update interval
    hass.data[DOMAIN][entry.entry_id][DATA_WLED_TIMER] = async_track_time_interval(
        hass, interval_update, SCAN_INTERVAL
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload WLED config entry."""

    # Cancel update timer for this entry/device.
    cancel_timer = hass.data[DOMAIN][entry.entry_id][DATA_WLED_TIMER]
    cancel_timer()

    # Unload entities for this entry/device.
    await asyncio.gather(
        *(
            hass.config_entries.async_forward_entry_unload(entry, component)
            for component in WLED_COMPONENTS
        )
    )

    # Cleanup
    del hass.data[DOMAIN][entry.entry_id]
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return True


class WLEDEntity(Entity):
    """Defines a base WLED entity."""

    def __init__(
        self,
        entry_id: str,
        wled: WLED,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the WLED entity."""
        self._attributes: Dict[str, Union[str, int, float]] = {}
        self._available = True
        self._enabled_default = enabled_default
        self._entry_id = entry_id
        self._icon = icon
        self._name = name
        self._unsub_dispatcher = None
        self.wled = wled

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        return self._attributes

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, DATA_WLED_UPDATED, self._schedule_immediate_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from update signal."""
        self._unsub_dispatcher()

    @callback
    def _schedule_immediate_update(self, entry_id: str) -> None:
        """Schedule an immediate update of the entity."""
        if entry_id == self._entry_id:
            self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update WLED entity."""
        if not self.enabled:
            return

        if self.wled.device is None:
            self._available = False
            return

        self._available = True
        await self._wled_update()

    async def _wled_update(self) -> None:
        """Update WLED entity."""
        raise NotImplementedError()


class WLEDDeviceEntity(WLEDEntity):
    """Defines a WLED device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this WLED device."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.wled.device.info.mac_address)},
            ATTR_NAME: self.wled.device.info.name,
            ATTR_MANUFACTURER: self.wled.device.info.brand,
            ATTR_MODEL: self.wled.device.info.product,
            ATTR_SOFTWARE_VERSION: self.wled.device.info.version,
        }
