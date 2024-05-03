"""Support for Lutron Homeworks Series 4 and 8 systems."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from pyhomeworks.pyhomeworks import HW_BUTTON_PRESSED, HW_BUTTON_RELEASED, Homeworks
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import (
    CONF_ADDR,
    CONF_CONTROLLER_ID,
    CONF_DIMMERS,
    CONF_KEYPADS,
    CONF_RATE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.LIGHT]

CONF_COMMAND = "command"

EVENT_BUTTON_PRESS = "homeworks_button_press"
EVENT_BUTTON_RELEASE = "homeworks_button_release"

DEFAULT_FADE_RATE = 1.0

KEYPAD_LEDSTATE_POLL_COOLDOWN = 1.0

CV_FADE_RATE = vol.All(vol.Coerce(float), vol.Range(min=0, max=20))

DIMMER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDR): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_RATE, default=DEFAULT_FADE_RATE): CV_FADE_RATE,
    }
)

KEYPAD_SCHEMA = vol.Schema(
    {vol.Required(CONF_ADDR): cv.string, vol.Required(CONF_NAME): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Required(CONF_DIMMERS): vol.All(cv.ensure_list, [DIMMER_SCHEMA]),
                vol.Optional(CONF_KEYPADS, default=[]): vol.All(
                    cv.ensure_list, [KEYPAD_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONTROLLER_ID): str,
        vol.Required(CONF_COMMAND): vol.All(cv.ensure_list, [str]),
    }
)


@dataclass
class HomeworksData:
    """Container for config entry data."""

    controller: Homeworks
    controller_id: str
    keypads: dict[str, HomeworksKeypad]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Lutron Homeworks Series 4 and 8 integration."""

    async def async_call_service(service_call: ServiceCall) -> None:
        """Call the service."""
        await async_send_command(hass, service_call.data)

    hass.services.async_register(
        DOMAIN,
        "send_command",
        async_call_service,
        schema=SERVICE_SEND_COMMAND_SCHEMA,
    )


async def async_send_command(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Send command to a controller."""

    def get_controller_ids() -> list[str]:
        """Get homeworks data for the specified controller ID."""
        return [data.controller_id for data in hass.data[DOMAIN].values()]

    def get_homeworks_data(controller_id: str) -> HomeworksData | None:
        """Get homeworks data for the specified controller ID."""
        data: HomeworksData
        for data in hass.data[DOMAIN].values():
            if data.controller_id == controller_id:
                return data
        return None

    homeworks_data = get_homeworks_data(data[CONF_CONTROLLER_ID])
    if not homeworks_data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_controller_id",
            translation_placeholders={
                "controller_id": data[CONF_CONTROLLER_ID],
                "controller_ids": ",".join(get_controller_ids()),
            },
        )

    commands = data[CONF_COMMAND]
    _LOGGER.debug("Send commands: %s", commands)
    for command in commands:
        if command.lower().startswith("delay"):
            delay = int(command.partition(" ")[2])
            _LOGGER.debug("Sleeping for %s ms", delay)
            await asyncio.sleep(delay / 1000)
        else:
            _LOGGER.debug("Sending command '%s'", command)
            await hass.async_add_executor_job(
                # pylint: disable-next=protected-access
                homeworks_data.controller._send,
                command,
            )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Start Homeworks controller."""

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homeworks from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    controller_id = entry.options[CONF_CONTROLLER_ID]

    def hw_callback(msg_type: Any, values: Any) -> None:
        """Dispatch state changes."""
        _LOGGER.debug("callback: %s, %s", msg_type, values)
        addr = values[0]
        signal = f"homeworks_entity_{controller_id}_{addr}"
        dispatcher_send(hass, signal, msg_type, values)

    config = entry.options
    try:
        controller = await hass.async_add_executor_job(
            Homeworks, config[CONF_HOST], config[CONF_PORT], hw_callback
        )
    except (ConnectionError, OSError) as err:
        raise ConfigEntryNotReady from err

    def cleanup(event: Event) -> None:
        controller.close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup))

    keypads: dict[str, HomeworksKeypad] = {}
    for key_config in config.get(CONF_KEYPADS, []):
        addr = key_config[CONF_ADDR]
        name = key_config[CONF_NAME]
        keypads[addr] = HomeworksKeypad(hass, controller, controller_id, addr, name)

    hass.data[DOMAIN][entry.entry_id] = HomeworksData(
        controller, controller_id, keypads
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    data: HomeworksData = hass.data[DOMAIN].pop(entry.entry_id)
    for keypad in data.keypads.values():
        keypad.unsubscribe()

    await hass.async_add_executor_job(data.controller.close)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def calculate_unique_id(controller_id: str, addr: str, idx: int) -> str:
    """Calculate entity unique id."""
    return f"homeworks.{controller_id}.{addr}.{idx}"


class HomeworksEntity(Entity):
    """Base class of a Homeworks device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        controller: Homeworks,
        controller_id: str,
        addr: str,
        idx: int,
        name: str | None,
    ) -> None:
        """Initialize Homeworks device."""
        self._addr = addr
        self._idx = idx
        self._controller_id = controller_id
        self._attr_name = name
        self._attr_unique_id = calculate_unique_id(
            self._controller_id, self._addr, self._idx
        )
        self._controller = controller
        self._attr_extra_state_attributes = {"homeworks_address": self._addr}


class HomeworksKeypad:
    """When you want signals instead of entities.

    Stateless sensors such as keypads are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        controller: Homeworks,
        controller_id: str,
        addr: str,
        name: str,
    ) -> None:
        """Register callback that will be used for signals."""
        self._addr = addr
        self._controller = controller
        self._debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=KEYPAD_LEDSTATE_POLL_COOLDOWN,
            immediate=False,
            function=self._request_keypad_led_states,
        )
        self._hass = hass
        self._name = name
        self._id = slugify(self._name)
        signal = f"homeworks_entity_{controller_id}_{self._addr}"
        _LOGGER.debug("connecting %s", signal)
        self.unsubscribe = async_dispatcher_connect(
            self._hass, signal, self._update_callback
        )

    @callback
    def _update_callback(self, msg_type: str, values: list[Any]) -> None:
        """Fire events if button is pressed or released."""

        if msg_type == HW_BUTTON_PRESSED:
            event = EVENT_BUTTON_PRESS
        elif msg_type == HW_BUTTON_RELEASED:
            event = EVENT_BUTTON_RELEASE
        else:
            return
        data = {CONF_ID: self._id, CONF_NAME: self._name, "button": values[1]}
        self._hass.bus.async_fire(event, data)

    def _request_keypad_led_states(self) -> None:
        """Query keypad led state."""
        # pylint: disable-next=protected-access
        self._controller._send(f"RKLS, {self._addr}")

    async def request_keypad_led_states(self) -> None:
        """Query keypad led state.

        Debounced to not storm the controller during setup.
        """
        await self._debouncer.async_call()
