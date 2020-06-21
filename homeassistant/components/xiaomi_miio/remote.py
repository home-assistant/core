"""Support for the Xiaomi IR Remote (Chuangmi IR)."""
import asyncio
from datetime import timedelta
import logging
import time

from miio import ChuangmiIr, DeviceException  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    PLATFORM_SCHEMA,
    RemoteEntity,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_HOST,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_TOKEN,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.util.dt import utcnow

from .const import SERVICE_LEARN, SERVICE_SET_LED_OFF, SERVICE_SET_LED_ON

_LOGGER = logging.getLogger(__name__)

DATA_KEY = "remote.xiaomi_miio"

CONF_SLOT = "slot"
CONF_COMMANDS = "commands"

DEFAULT_TIMEOUT = 10
DEFAULT_SLOT = 1

COMMAND_SCHEMA = vol.Schema(
    {vol.Required(CONF_COMMAND): vol.All(cv.ensure_list, [cv.string])}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
            int, vol.Range(min=0)
        ),
        vol.Optional(CONF_SLOT, default=DEFAULT_SLOT): vol.All(
            int, vol.Range(min=1, max=1000000)
        ),
        vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
        vol.Optional(CONF_COMMANDS, default={}): cv.schema_with_slug_keys(
            COMMAND_SCHEMA
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Xiaomi IR Remote (Chuangmi IR) platform."""
    host = config[CONF_HOST]
    token = config[CONF_TOKEN]

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    # The Chuang Mi IR Remote Controller wants to be re-discovered every
    # 5 minutes. As long as polling is disabled the device should be
    # re-discovered (lazy_discover=False) in front of every command.
    device = ChuangmiIr(host, token, lazy_discover=False)

    # Check that we can communicate with device.
    try:
        device_info = await hass.async_add_executor_job(device.info)
        model = device_info.model
        unique_id = f"{model}-{device_info.mac_address}"
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )
    except DeviceException as ex:
        _LOGGER.error("Device unavailable or token incorrect: %s", ex)
        raise PlatformNotReady

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    friendly_name = config.get(CONF_NAME, f"xiaomi_miio_{host.replace('.', '_')}")
    slot = config.get(CONF_SLOT)
    timeout = config.get(CONF_TIMEOUT)

    xiaomi_miio_remote = XiaomiMiioRemote(
        friendly_name, device, unique_id, slot, timeout, config.get(CONF_COMMANDS)
    )

    hass.data[DATA_KEY][host] = xiaomi_miio_remote

    async_add_entities([xiaomi_miio_remote])

    async def async_service_led_off_handler(entity, service):
        """Handle set_led_off command."""
        await hass.async_add_executor_job(entity.device.set_indicator_led, False)

    async def async_service_led_on_handler(entity, service):
        """Handle set_led_on command."""
        await hass.async_add_executor_job(entity.device.set_indicator_led, True)

    async def async_service_learn_handler(entity, service):
        """Handle a learn command."""
        device = entity.device

        slot = service.data.get(CONF_SLOT, entity.slot)

        await hass.async_add_executor_job(device.learn, slot)

        timeout = service.data.get(CONF_TIMEOUT, entity.timeout)

        _LOGGER.info("Press the key you want Home Assistant to learn")
        start_time = utcnow()
        while (utcnow() - start_time) < timedelta(seconds=timeout):
            message = await hass.async_add_executor_job(device.read, slot)
            _LOGGER.debug("Message received from device: '%s'", message)

            if "code" in message and message["code"]:
                log_msg = "Received command is: {}".format(message["code"])
                _LOGGER.info(log_msg)
                hass.components.persistent_notification.async_create(
                    log_msg, title="Xiaomi Miio Remote"
                )
                return

            if "error" in message and message["error"]["message"] == "learn timeout":
                await hass.async_add_executor_job(device.learn, slot)

            await asyncio.sleep(1)

        _LOGGER.error("Timeout. No infrared command captured")
        hass.components.persistent_notification.async_create(
            "Timeout. No infrared command captured", title="Xiaomi Miio Remote"
        )

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_LEARN,
        {
            vol.Optional(CONF_TIMEOUT, default=10): vol.All(int, vol.Range(min=0)),
            vol.Optional(CONF_SLOT, default=1): vol.All(
                int, vol.Range(min=1, max=1000000)
            ),
        },
        async_service_learn_handler,
    )
    platform.async_register_entity_service(
        SERVICE_SET_LED_ON, {}, async_service_led_on_handler,
    )
    platform.async_register_entity_service(
        SERVICE_SET_LED_OFF, {}, async_service_led_off_handler,
    )


class XiaomiMiioRemote(RemoteEntity):
    """Representation of a Xiaomi Miio Remote device."""

    def __init__(self, friendly_name, device, unique_id, slot, timeout, commands):
        """Initialize the remote."""
        self._name = friendly_name
        self._device = device
        self._unique_id = unique_id
        self._slot = slot
        self._timeout = timeout
        self._state = False
        self._commands = commands

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the remote."""
        return self._name

    @property
    def device(self):
        """Return the remote object."""
        return self._device

    @property
    def slot(self):
        """Return the slot to save learned command."""
        return self._slot

    @property
    def timeout(self):
        """Return the timeout for learning command."""
        return self._timeout

    @property
    def is_on(self):
        """Return False if device is unreachable, else True."""
        try:
            self.device.info()
            return True
        except DeviceException:
            return False

    @property
    def should_poll(self):
        """We should not be polled for device up state."""
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        _LOGGER.error(
            "Device does not support turn_on, "
            "please use 'remote.send_command' to send commands."
        )

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.error(
            "Device does not support turn_off, "
            "please use 'remote.send_command' to send commands."
        )

    def _send_command(self, payload):
        """Send a command."""
        _LOGGER.debug("Sending payload: '%s'", payload)
        try:
            self.device.play(payload)
        except DeviceException as ex:
            _LOGGER.error(
                "Transmit of IR command failed, %s, exception: %s", payload, ex
            )

    def send_command(self, command, **kwargs):
        """Send a command."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS)

        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        for _ in range(num_repeats):
            for payload in command:
                if payload in self._commands:
                    for local_payload in self._commands[payload][CONF_COMMAND]:
                        self._send_command(local_payload)
                else:
                    self._send_command(payload)
                time.sleep(delay)
