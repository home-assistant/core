"""Config flow to configure songpal component."""
import logging
from typing import Optional
from urllib.parse import urlparse

from songpal import Device, SongpalException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import CONF_ENDPOINT, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = "Songpal device"


class SongpalConfig:
    """Device Configuration."""

    def __init__(self, name, host, endpoint):
        """Initialize Configuration."""
        self.name = name
        self.host = host
        self.endpoint = endpoint


class SongpalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Songpal configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the flow."""
        self.conf: Optional[SongpalConfig] = None

    async def _show_setup_form(self, user_input=None, errors=None):
        user_input = user_input or {}
        default_name = user_input.get(CONF_NAME) or DEFAULT_NAME
        default_endpoint = user_input.get(CONF_ENDPOINT)
        data_schema = {
            vol.Optional(CONF_NAME, default=default_name): str,
        }
        if default_endpoint is not None:
            data_schema.update(
                {vol.Required(CONF_ENDPOINT, default=default_endpoint): str}
            )
        else:
            data_schema.update({vol.Required(CONF_ENDPOINT): str})
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form()

        # Validate input
        name = user_input.get(CONF_NAME)
        if not name:
            name = DEFAULT_NAME
        endpoint = user_input[CONF_ENDPOINT]
        parsed_url = urlparse(endpoint)
        self.conf = SongpalConfig(name, parsed_url.hostname, endpoint)

        errors = await self._async_try_connect()
        if errors is not None:
            return await self._show_setup_form(user_input, errors)

        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        # Check if already configured
        if self._endpoint_already_configured():
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(self.conf.endpoint)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                description_placeholders={
                    CONF_NAME: self.conf.name,
                    CONF_HOST: self.conf.host,
                },
            )

        return self.async_create_entry(
            title=self.conf.name,
            data={CONF_NAME: self.conf.name, CONF_ENDPOINT: self.conf.endpoint},
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Songpal device."""
        await self.async_set_unique_id(discovery_info[ssdp.ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Discovered: %s", discovery_info)

        friendly_name = discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME]
        parsed_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])
        scalarweb_info = discovery_info["X_ScalarWebAPI_DeviceInfo"]
        endpoint = scalarweb_info["X_ScalarWebAPI_BaseURL"]
        service_types = scalarweb_info["X_ScalarWebAPI_ServiceList"][
            "X_ScalarWebAPI_ServiceType"
        ]

        # Ignore Bravia TVs
        if "videoScreen" in service_types:
            return self.async_abort(reason="not_songpal_device")

        # pylint: disable=no-member
        self.context["title_placeholders"] = {
            CONF_NAME: friendly_name,
            CONF_HOST: parsed_url.hostname,
        }

        self.conf = SongpalConfig(friendly_name, parsed_url.hostname, endpoint)

        return await self.async_step_init()

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        name = user_input.get(CONF_NAME)
        endpoint = user_input.get(CONF_ENDPOINT)
        parsed_url = urlparse(endpoint)
        self.conf = SongpalConfig(name, parsed_url.hostname, endpoint)

        errors = await self._async_try_connect()
        if errors is not None:
            _LOGGER.error(
                "Unable to import songpal configuration (%s: %s). Please check your endpoint.",
                name,
                endpoint,
            )
            return self.async_abort(reason="connection")

        return await self.async_step_init(user_input)

    async def _async_try_connect(self):
        """Try to connect and return errors."""
        try:
            device = Device(self.conf.endpoint)
            await device.get_supported_methods()
        except SongpalException as ex:
            _LOGGER.debug("Connection failed: %s", ex)
            return {"base": "connection"}
        return None

    def _endpoint_already_configured(self):
        """See if we already have an endpoint matching user input configured."""
        existing_endpoints = {
            entry.data[CONF_ENDPOINT] for entry in self._async_current_entries()
        }
        return self.conf.endpoint in existing_endpoints
