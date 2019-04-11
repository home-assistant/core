"""Home Assistant Switcher Component."""

from asyncio import TimeoutError as Asyncio_TimeoutError, wait_for
from datetime import datetime
from logging import getLogger
from typing import Dict, Optional

import voluptuous as vol

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_ICON, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import async_call_later

_LOGGER = getLogger(__name__)

REQUIREMENTS = ['aioswitcher==2019.3.21']

DOMAIN = 'switcher_kis'

CONF_DEVICE_ID = 'device_id'
CONF_DEVICE_PASSWORD = 'device_password'
CONF_PHONE_ID = 'phone_id'

DEFAULT_NAME = 'boiler'

DISCOVERY_CONFIG = 'config'
DISCOVERY_DEVICE = 'device'

EVENT_SWITCHER_DEVICE_UPDATED = 'switcher_device_update'
UPDATED_DEVICE = 'updated_device'

ATTR_AUTO_OFF_SET = 'auto_off_set'
ATTR_DEVICE_NAME = 'device_name'
ATTR_ELECTRIC_CURRNET = 'electric_current'
ATTR_IP_ADDRESS = 'ip_address'
ATTR_LAST_DATA_UPDATE = 'last_data_update'
ATTR_LAST_STATE_CHANGE = 'last_state_change'
ATTR_REMAINING_TIME = 'remaining_time'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PHONE_ID): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DEVICE_PASSWORD): cv.string,
        vol.Optional(CONF_NAME,
                     default=DEFAULT_NAME): cv.slugify,
        vol.Optional(CONF_ICON): cv.icon
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the switcher component."""
    from aioswitcher.bridge import SwitcherV2Bridge

    phone_id = config[DOMAIN][CONF_PHONE_ID]
    device_id = config[DOMAIN][CONF_DEVICE_ID]
    device_password = config[DOMAIN][CONF_DEVICE_PASSWORD]

    v2bridge = SwitcherV2Bridge(
        hass.loop, phone_id, device_id, device_password)

    await v2bridge.start()

    async def async_stop_bridge(event: Event) -> None:
        """On homeassistant stop, gracefully stop the bridge if running."""
        await v2bridge.stop()
        return None

    hass.async_add_job(hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_stop_bridge))

    try:
        device_data = await wait_for(
            v2bridge.queue.get(), timeout=5.0, loop=hass.loop)
    except (Asyncio_TimeoutError, RuntimeError):
        _LOGGER.exception("failed to get response from device")
        return False

    hass.data[DOMAIN] = {
        DISCOVERY_CONFIG: config[DOMAIN],
        DISCOVERY_DEVICE: device_data
    }

    await hass.async_create_task(async_load_platform(
        hass, SWITCH_DOMAIN, DOMAIN, None, config))

    async def device_updates(timestamp: Optional[datetime]) -> None:
        """Use for updating the device data from the queue."""
        if v2bridge.running:
            device_new_data = await v2bridge.queue.get()
            if device_new_data:
                hass.bus.async_fire(EVENT_SWITCHER_DEVICE_UPDATED,
                                    {UPDATED_DEVICE: device_new_data})
            async_call_later(hass, 3, device_updates)
        return None

    async_call_later(hass, 3, device_updates)

    return True
