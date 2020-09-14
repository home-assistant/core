"""Config flow for Aruba Instant integration."""
import logging

from instantpy import InstantVC
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (  # pylint:disable=unused-import
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    DISCOVERED_DEVICES
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


async def async_validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    instant_vc = InstantVC(
        data.get("host"),
        data.get("username"),
        data.get("password"),
        port=data.get("port"),
        ssl_verify=data.get("verify_ssl"),
    )

    connection = await hass.async_add_executor_job(instant_vc.login)
    if connection is True:
        if instant_vc.logged_in is False:
            raise InvalidAuth
    elif "[SSL: CERTIFICATE_VERIFY_FAILED]" in connection.args[0].args[0]:
        raise CannotVerifySSLCert
    else:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": "Aruba Instant VC", "vc": instant_vc}


@config_entries.HANDLERS.register(DOMAIN)
class InstantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aruba Instant."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return InstantOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                self.config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_PORT: user_input.get(CONF_PORT),
                    CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL),
                }
                await self.async_set_unique_id(user_input[CONF_HOST])
                info = await async_validate_input(self.hass, user_input)
                return await self.async_step_track_clients(config_input=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotVerifySSLCert:
                errors["base"] = "cannot_verify_ssl_cert"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_track_clients(self, user_input=None, config_input=None):
        """Handles tracking clients on initial component setup."""
        errors = {}
        data = {}
        if user_input is not None:
            self.config['options'] = list(user_input.get('clients'))
            data.update(self.config)
            data.update(user_input)
            return self.async_create_entry(title="Aruba Instant VC", data=data)
        instant_vc = InstantVC(
            self.config.get("host"),
            self.config.get("username"),
            self.config.get("password"),
            port=self.config.get("port"),
            ssl_verify=self.config.get("verify_ssl"),
        )
        clients = await self.hass.async_add_executor_job(instant_vc.clients)
        macs = {client: f"{clients[client]['name']} ({client})" for client in clients}
        track_client_data_schema = vol.Schema(
            {
                vol.Optional("clients", description="Clients",): cv.multi_select(macs),
                vol.Optional(
                    "track_none", description="Stop tracking all devices."
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="track_clients", data_schema=track_client_data_schema, errors=errors
        )


class InstantOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Aruba Instant options."""

    def __init__(self, config_entry):
        """Initialize Aruba Instant options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Handle client tracking."""
        errors = {}
        if user_input is not None:
            selected_macs = {
                mac: f"{self.hass.data[DOMAIN]['coordinator'][self.config_entry.entry_id].data.get(mac)['name']} ({mac})"
                for mac in user_input.get("clients")
            }
            for mac in selected_macs.keys():
                entity = self.hass.data[DOMAIN]["coordinator"][
                    self.config_entry.entry_id
                ].data.get(mac)
                self.options.update({mac: entity.get('mac')})
                if user_input.get("track_none"):
                    return self.async_create_entry(title="", data={"track_none": True})
            return self.async_create_entry(title="", data=selected_macs)
        macs = {}
        for mac in self.hass.data[DOMAIN][DISCOVERED_DEVICES][self.config_entry.entry_id]:
            if mac in self.hass.data[DOMAIN]['coordinator'][self.config_entry.entry_id].data.keys():
                macs.update({mac: f"{self.hass.data[DOMAIN]['coordinator'][self.config_entry.entry_id].data.get(mac)['name']} ({mac})"})

        macs = dict(sorted(macs.items(), key=lambda x: x[1].lower()))
        track_client_data_schema = vol.Schema(
            {
                vol.Optional(
                    "clients",
                    description="Clients",
                    default=set(self.hass.data[DOMAIN]['coordinator'][self.config_entry.entry_id].entities.keys()),
                ): cv.multi_select(macs),
                vol.Optional(
                    "track_none", description="Stop tracking all devices."
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=track_client_data_schema, errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotVerifySSLCert(exceptions.HomeAssistantError):
    """Error to indicate an issue validating an SSL certificate."""
