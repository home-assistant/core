"""Adds config flow for Brother Printer."""
import ipaddress
import re

from brother import Brother, SnmpError, UnsupportedModel
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_TYPE

from .const import DOMAIN, PRINTER_TYPES  # pylint:disable=unused-import

DATA_SCHEMA = vol.Schema(
    {
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
        return all(x and not disallowed.search(x) for x in host.split("."))


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

                await self.async_set_unique_id(brother.serial.lower())
                self._abort_if_unique_id_configured()

                title = f"{brother.model} {brother.serial}"
                return self.async_create_entry(title=title, data=user_input)
            except InvalidHost:
                errors[CONF_HOST] = "wrong_host"
            except ConnectionError:
                errors["base"] = "connection_error"
            except SnmpError:
                errors["base"] = "snmp_error"
            except UnsupportedModel:
                return self.async_abort(reason="unsupported_model")

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(self, user_input=None):
        """Handle zeroconf discovery."""
        if user_input is None:
            return self.async_abort(reason="connection_error")

        if "Brother" not in user_input["name"]:
            return self.async_abort(reason="not_brother_printer")

        # Hostname is format: brother.local.
        host = user_input["hostname"].rstrip(".")

        try:
            brother = Brother(host)
            await brother.async_update()
        except (ConnectionError, SnmpError, UnsupportedModel):
            return self.async_abort(reason="connection_error")

        # Check if already configured
        await self.async_set_unique_id(brother.serial.lower())
        self._abort_if_unique_id_configured()

        self.context.update(
            {
                CONF_HOST: host,
                "title_placeholders": {
                    "serial_number": brother.serial,
                    "model": brother.model,
                },
            }
        )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_TYPE, default="laser"): vol.In(PRINTER_TYPES)}
            ),
            description_placeholders={
                "serial_number": brother.serial,
                "model": brother.model,
            },
        )

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Handle a flow initiated by zeroconf."""
        try:
            brother = Brother(self.context.get(CONF_HOST))
            await brother.async_update()
        except (ConnectionError, SnmpError, UnsupportedModel):
            return self.async_abort(reason="connection_error")
        if user_input is not None:

            # Check if already configured
            await self.async_set_unique_id(brother.serial.lower())
            self._abort_if_unique_id_configured()

            title = f"{brother.model} {brother.serial}"
            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: self.context.get(CONF_HOST),
                    CONF_TYPE: user_input[CONF_TYPE],
                },
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_TYPE, default="laser"): vol.In(PRINTER_TYPES)}
            ),
            description_placeholders={
                "serial_number": brother.serial,
                "model": brother.model,
            },
        )


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate that hostname/IP address is invalid."""
