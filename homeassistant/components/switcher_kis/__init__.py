"""Home Assistant Switcher Component."""

from asyncio import QueueEmpty, TimeoutError as Asyncio_TimeoutError, wait_for
from datetime import datetime, timedelta
from logging import getLogger
from typing import Dict, Optional

import voluptuous as vol

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import EventType, HomeAssistantType

_LOGGER = getLogger(__name__)

DOMAIN = 'switcher_kis'

CONF_DEVICE_ID = 'device_id'
CONF_DEVICE_PASSWORD = 'device_password'
CONF_PHONE_ID = 'phone_id'

DATA_DEVICE = 'device'

SIGNAL_SWITCHER_DEVICE_UPDATE = 'switcher_device_update'

ATTR_AUTO_OFF_SET = 'auto_off_set'
ATTR_ELECTRIC_CURRENT = 'electric_current'
ATTR_REMAINING_TIME = 'remaining_time'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PHONE_ID): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DEVICE_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, config: Dict) -> bool:
    """Set up the switcher component."""
    from aioswitcher.bridge import SwitcherV2Bridge

    phone_id = config[DOMAIN][CONF_PHONE_ID]
    device_id = config[DOMAIN][CONF_DEVICE_ID]
    device_password = config[DOMAIN][CONF_DEVICE_PASSWORD]

    v2bridge = SwitcherV2Bridge(
        hass.loop, phone_id, device_id, device_password)

    await v2bridge.start()

    async def async_stop_bridge(event: EventType) -> None:
        """On homeassistant stop, gracefully stop the bridge if running."""
        await v2bridge.stop()

    hass.async_add_job(hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_stop_bridge))

    try:
        device_data = await wait_for(
            v2bridge.queue.get(), timeout=5.0, loop=hass.loop)
    except (Asyncio_TimeoutError, RuntimeError):
        _LOGGER.exception("failed to get response from device")
        await v2bridge.stop()
        return False

    hass.data[DOMAIN] = {
        DATA_DEVICE: device_data
    }

    hass.async_create_task(async_load_platform(
        hass, SWITCH_DOMAIN, DOMAIN, None, config))

    @callback
    def device_updates(timestamp: Optional[datetime]) -> None:
        """Use for updating the device data from the queue."""
        if v2bridge.running:
            try:
                device_new_data = v2bridge.queue.get_nowait()
                if device_new_data:
                    async_dispatcher_send(
                        hass, SIGNAL_SWITCHER_DEVICE_UPDATE, device_new_data)
            except QueueEmpty:
                pass

    async_track_time_interval(hass, device_updates, timedelta(seconds=4))

    return True
