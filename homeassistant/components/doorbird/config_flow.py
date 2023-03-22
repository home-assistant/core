"""Config flow for DoorBird integration."""
from __future__ import annotations

from http import HTTPStatus
from ipaddress import ip_address
import logging

from doorbirdpy import DoorBird
import requests
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.util.network import is_ipv4_address, is_link_local

from .const import CONF_EVENTS, DOMAIN, DOORBIRD_OUI
from .util import get_mac_address_from_doorstation_info

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(host=None, name=None):
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_NAME, default=name): str,
        }
    )


def _check_device(device):
    """Verify we can connect to the device and return the status."""
    return device.ready(), device.info()


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    device = DoorBird(data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
    try:
        status, info = await hass.async_add_executor_job(_check_device, device)
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise InvalidAuth from err
        raise CannotConnect from err
    except OSError as err:
        raise CannotConnect from err

    if not status[0]:
        raise CannotConnect

    mac_addr = get_mac_address_from_doorstation_info(info)

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_HOST], "mac_addr": mac_addr}


async def async_verify_supported_device(hass, host):
    """Verify the doorbell state endpoint returns a 401."""
    device = DoorBird(host, "", "")
    try:
        await hass.async_add_executor_job(device.doorbell_state)
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == HTTPStatus.UNAUTHORIZED:
            return True
    except OSError:
        return False
    return False


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DoorBird."""

    VERSION = 1

    def __init__(self):
        """Initialize the DoorBird config flow."""
        self.discovery_schema = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)
            if not errors:
                await self.async_set_unique_id(info["mac_addr"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        data = self.discovery_schema or _schema_with_defaults()
        return self.async_show_form(step_id="user", data_schema=data, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Prepare configuration for a discovered doorbird device."""
        macaddress = discovery_info.properties["macaddress"]
        host = discovery_info.host

        if macaddress[:6] != DOORBIRD_OUI:
            return self.async_abort(reason="not_doorbird_device")
        if is_link_local(ip_address(host)):
            return self.async_abort(reason="link_local_address")
        if not is_ipv4_address(host):
            return self.async_abort(reason="not_ipv4_address")

        await self.async_set_unique_id(macaddress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._async_abort_entries_match({CONF_HOST: host})

        if not await async_verify_supported_device(self.hass, host):
            return self.async_abort(reason="not_doorbird_device")

        chop_ending = "._axis-video._tcp.local."
        friendly_hostname = discovery_info.name.removesuffix(chop_ending)

        self.context["title_placeholders"] = {
            CONF_NAME: friendly_hostname,
            CONF_HOST: host,
        }
        self.discovery_schema = _schema_with_defaults(host=host, name=friendly_hostname)

        return await self.async_step_user()

    async def _async_validate_or_error(self, user_input):
        """Validate doorbird or error."""
        errors = {}
        info = {}
        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return info, errors

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for doorbird."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            events = [event.strip() for event in user_input[CONF_EVENTS].split(",")]

            return self.async_create_entry(title="", data={CONF_EVENTS: events})

        current_events = self.config_entry.options.get(CONF_EVENTS, [])

        # We convert to a comma separated list for the UI
        # since there really isn't anything better
        options_schema = vol.Schema(
            {vol.Optional(CONF_EVENTS, default=", ".join(current_events)): str}
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
