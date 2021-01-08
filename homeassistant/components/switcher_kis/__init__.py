"""Home Assistant Switcher Component."""
from asyncio import QueueEmpty, TimeoutError as Asyncio_TimeoutError, wait_for
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional

from aioswitcher.api import SwitcherV2Api
from aioswitcher.bridge import SwitcherV2Bridge
from aioswitcher.consts import COMMAND_ON
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_EDIT
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback, split_entity_id
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_listen_platform, async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import (
    ContextType,
    DiscoveryInfoType,
    EventType,
    HomeAssistantType,
    ServiceCallType,
)
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = "switcher_kis"

CONF_AUTO_OFF = "auto_off"
CONF_TIMER_MINUTES = "timer_minutes"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_PASSWORD = "device_password"
CONF_PHONE_ID = "phone_id"

DATA_DEVICE = "device"

SIGNAL_SWITCHER_DEVICE_UPDATE = "switcher_device_update"

ATTR_AUTO_OFF_SET = "auto_off_set"
ATTR_ELECTRIC_CURRENT = "electric_current"
ATTR_REMAINING_TIME = "remaining_time"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PHONE_ID): cv.string,
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(CONF_DEVICE_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SET_AUTO_OFF_NAME = "set_auto_off"
SERVICE_SET_AUTO_OFF_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_AUTO_OFF): cv.time_period_str,
    }
)

SERVICE_TURN_ON_WITH_TIMER_NAME = "turn_on_with_timer"
SERVICE_TURN_ON_WITH_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TIMER_MINUTES): vol.All(
            cv.positive_int, vol.Range(min=1, max=90)
        ),
    }
)


@bind_hass
async def _validate_edit_permission(
    hass: HomeAssistantType, context: ContextType, entity_id: str
) -> None:
    """Use for validating user control permissions."""
    splited = split_entity_id(entity_id)
    if splited[0] != SWITCH_DOMAIN or not splited[1].startswith(DOMAIN):
        raise Unauthorized(context=context, entity_id=entity_id, permission=POLICY_EDIT)
    user = await hass.auth.async_get_user(context.user_id)
    if user is None:
        raise UnknownUser(context=context, entity_id=entity_id, permission=POLICY_EDIT)
    if not user.permissions.check_entity(entity_id, POLICY_EDIT):
        raise Unauthorized(context=context, entity_id=entity_id, permission=POLICY_EDIT)


async def async_setup(hass: HomeAssistantType, config: Dict) -> bool:
    """Set up the switcher component."""

    phone_id = config[DOMAIN][CONF_PHONE_ID]
    device_id = config[DOMAIN][CONF_DEVICE_ID]
    device_password = config[DOMAIN][CONF_DEVICE_PASSWORD]

    v2bridge = SwitcherV2Bridge(hass.loop, phone_id, device_id, device_password)

    await v2bridge.start()

    async def async_stop_bridge(event: EventType) -> None:
        """On Home Assistant stop, gracefully stop the bridge if running."""
        await v2bridge.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_bridge)

    try:
        device_data = await wait_for(v2bridge.queue.get(), timeout=10.0)
    except (Asyncio_TimeoutError, RuntimeError):
        _LOGGER.exception("Failed to get response from device")
        await v2bridge.stop()
        return False
    hass.data[DOMAIN] = {DATA_DEVICE: device_data}

    async def async_switch_platform_discovered(
        platform: str, discovery_info: DiscoveryInfoType
    ) -> None:
        """Use for registering services after switch platform is discovered."""
        if platform != DOMAIN:
            return

        async def async_set_auto_off_service(service: ServiceCallType) -> None:
            """Use for handling setting device auto-off service calls."""

            await _validate_edit_permission(
                hass, service.context, service.data[ATTR_ENTITY_ID]
            )

            async with SwitcherV2Api(
                hass.loop, device_data.ip_addr, phone_id, device_id, device_password
            ) as swapi:
                await swapi.set_auto_shutdown(service.data[CONF_AUTO_OFF])

        async def async_turn_on_with_timer_service(service: ServiceCallType) -> None:
            """Use for handling turning device on with a timer service calls."""

            await _validate_edit_permission(
                hass, service.context, service.data[ATTR_ENTITY_ID]
            )

            async with SwitcherV2Api(
                hass.loop, device_data.ip_addr, phone_id, device_id, device_password
            ) as swapi:
                await swapi.control_device(COMMAND_ON, service.data[CONF_TIMER_MINUTES])

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_AUTO_OFF_NAME,
            async_set_auto_off_service,
            schema=SERVICE_SET_AUTO_OFF_SCHEMA,
        )

        hass.services.async_register(
            DOMAIN,
            SERVICE_TURN_ON_WITH_TIMER_NAME,
            async_turn_on_with_timer_service,
            schema=SERVICE_TURN_ON_WITH_TIMER_SCHEMA,
        )

    async_listen_platform(hass, SWITCH_DOMAIN, async_switch_platform_discovered)

    hass.async_create_task(async_load_platform(hass, SWITCH_DOMAIN, DOMAIN, {}, config))

    @callback
    def device_updates(timestamp: Optional[datetime]) -> None:
        """Use for updating the device data from the queue."""
        if v2bridge.running:
            try:
                device_new_data = v2bridge.queue.get_nowait()
                if device_new_data:
                    async_dispatcher_send(
                        hass, SIGNAL_SWITCHER_DEVICE_UPDATE, device_new_data
                    )
            except QueueEmpty:
                pass

    async_track_time_interval(hass, device_updates, timedelta(seconds=4))

    return True
