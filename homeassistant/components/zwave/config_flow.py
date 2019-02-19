"""Config flow to configure Z-Wave."""
from collections import OrderedDict
import logging
import sys

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_USB_STICK_PATH, CONF_NETWORK_KEY,
    DEFAULT_CONF_USB_STICK_PATH, DOMAIN)

_LOGGER = logging.getLogger(__name__)


VENDOR_IDS = ('0658',)


def _get_z_stick():
    import serial.tools.list_ports

    for port in serial.tools.list_ports.comports(include_links=False):
        if port.vid is None:
            continue

        if port.manufacturer is not None:
            label = ' (' + port.manufacturer + ')'
        else:
            label = ''

        if port.product is not None and 'Zigbee' in port.product:
            continue
        if port.interface is not None and 'Zigbee' in port.interface:
            continue
        if port.description is not None and 'Zigbee' in port.description:
            continue

        for vid in VENDOR_IDS:
            if vid == hex(port.vid)[2:].zfill(4):
                if sys.platform.startswith('win'):
                    return '\\\\.\\' + port.device + label
                else:
                    return port.device + label

    return DEFAULT_CONF_USB_STICK_PATH


@config_entries.HANDLERS.register(DOMAIN)
class ZwaveFlowHandler(config_entries.ConfigFlow):
    """Handle a Z-Wave config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Z-Wave config flow."""
        self.usb_path = CONF_USB_STICK_PATH

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self._async_current_entries():
            return self.async_abort(reason='one_instance_only')

        errors = {}

        fields = OrderedDict()
        fields[vol.Required(CONF_USB_STICK_PATH,
                            default=_get_z_stick())] = str
        fields[vol.Optional(CONF_NETWORK_KEY)] = str

        if user_input is not None:
            # Check if USB path is valid
            from openzwave.option import ZWaveOption
            from openzwave.object import ZWaveException

            try:
                from functools import partial
                # pylint: disable=unused-variable
                port = user_input[CONF_USB_STICK_PATH]
                port = port.split('(')[0].strip()

                option = await self.hass.async_add_executor_job(  # noqa: F841
                    partial(ZWaveOption,
                            port,
                            user_path=self.hass.config.config_dir)
                )
                user_input[CONF_USB_STICK_PATH] = port

            except ZWaveException:
                errors['base'] = 'option_error'

                return self.async_show_form(
                    step_id='user',
                    data_schema=vol.Schema(fields),
                    errors=errors
                )

            if user_input.get(CONF_NETWORK_KEY) is None:
                # Generate a random key
                from random import choice
                key = str()
                for i in range(16):
                    key += '0x'
                    key += choice('1234567890ABCDEF')
                    key += choice('1234567890ABCDEF')
                    if i < 15:
                        key += ', '
                user_input[CONF_NETWORK_KEY] = key

            return self.async_create_entry(
                title='Z-Wave',
                data={
                    CONF_USB_STICK_PATH: user_input[CONF_USB_STICK_PATH],
                    CONF_NETWORK_KEY: user_input[CONF_NETWORK_KEY],
                },
            )

        return self.async_show_form(
            step_id='user', data_schema=vol.Schema(fields)
        )

    async def async_step_import(self, info):
        """Import existing configuration from Z-Wave."""
        if self._async_current_entries():
            return self.async_abort(reason='already_setup')

        return self.async_create_entry(
            title="Z-Wave (import from configuration.yaml)",
            data={
                CONF_USB_STICK_PATH: info.get(CONF_USB_STICK_PATH),
                CONF_NETWORK_KEY: info.get(CONF_NETWORK_KEY),
            },
        )
