"""Adds config flow for Brother Printer."""
import ipaddress
import logging
import re

from brother import Brother, SnmpError, UnsupportedModel
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers import device_registry

from .const import (  # pylint:disable=unused-import
    DEFAULT_NAME,
    DOMAIN,
    CONF_SENSORS,
    CONF_SERIAL,
    PRINTER_TYPES,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=""): str,
        vol.Optional(CONF_TYPE, default="laser"): vol.In(PRINTER_TYPES),
    }
)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == (4 or 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(map(lambda x: len(x) and not disallowed.search(x), host.split(".")))


async def configured_devices(hass, serial):
    """Return True if deice is already configured."""
    d_registry = await device_registry.async_get_registry(hass)
    for device in d_registry.devices.values():
        for item in device.identifiers:
            if serial in item:
                return True
    return False


@callback
def configured_instances(hass, condition):
    """Return a set of configured Brother instances."""
    return set(
        entry.data[condition] for entry in hass.config_entries.async_entries(DOMAIN)
    )


class BrotherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brother Printer."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                if not host_valid(user_input[CONF_HOST]):
                    raise InvalidHost()
                brother = Brother(user_input[CONF_HOST])
                await brother.async_update()
                if user_input[CONF_NAME] in configured_instances(self.hass, CONF_NAME):
                    raise NameExists()
                if await configured_devices(self.hass, brother.serial.lower()):
                    raise DeviceExists()

                sensors = []
                for sensor in SENSOR_TYPES:
                    if sensor in brother.data:
                        sensors.append(sensor)

                device_data = {
                    CONF_SERIAL: brother.serial.lower(),
                    CONF_SENSORS: sensors,
                }
                title = f"{brother.model} {brother.serial}"
                return self.async_create_entry(
                    title=title, data={**user_input, **device_data}
                )
            except InvalidHost:
                errors[CONF_HOST] = "wrong_host"
            except ConnectionError:
                errors["base"] = "connection_error"
            except NameExists:
                errors[CONF_NAME] = "name_exists"
            except DeviceExists:
                return self.async_abort(reason="device_exists")
            except SnmpError:
                errors["base"] = "snmp_error"
            except UnsupportedModel:
                return self.async_abort(reason="unsupported_model")

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""


class NameExists(exceptions.HomeAssistantError):
    """Error to indicate that name is already configured."""


class DeviceExists(exceptions.HomeAssistantError):
    """Error to indicate that device is already configured."""
