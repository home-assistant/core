"""Config flow to configure the Synology DSM integration."""
import logging
from urllib.parse import urlparse

from synology_dsm import SynologyDSM
from synology_dsm.exceptions import (
    SynologyDSMException,
    SynologyDSMLogin2SAFailedException,
    SynologyDSMLogin2SARequiredException,
    SynologyDSMLoginInvalidException,
    SynologyDSMRequestException,
)
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_DISKS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

from .const import CONF_VOLUMES, DEFAULT_PORT, DEFAULT_PORT_SSL, DEFAULT_SSL
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

CONF_OTP_CODE = "otp_code"


def _discovery_schema_with_defaults(discovery_info):
    return vol.Schema(_ordered_shared_schema(discovery_info))


def _user_schema_with_defaults(user_input):
    user_schema = {
        vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
    }
    user_schema.update(_ordered_shared_schema(user_input))

    return vol.Schema(user_schema)


def _ordered_shared_schema(schema_input):
    return {
        vol.Required(CONF_USERNAME, default=schema_input.get(CONF_USERNAME, "")): str,
        vol.Required(CONF_PASSWORD, default=schema_input.get(CONF_PASSWORD, "")): str,
        vol.Optional(CONF_PORT, default=schema_input.get(CONF_PORT, "")): str,
        vol.Optional(CONF_SSL, default=schema_input.get(CONF_SSL, DEFAULT_SSL)): bool,
    }


class SynologyDSMFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the synology_dsm config flow."""
        self.saved_user_input = {}
        self.discovered_conf = {}

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""
        if not user_input:
            user_input = {}

        if self.discovered_conf:
            user_input.update(self.discovered_conf)
            step_id = "link"
            data_schema = _discovery_schema_with_defaults(user_input)
        else:
            step_id = "user"
            data_schema = _user_schema_with_defaults(user_input)

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors or {},
            description_placeholders=self.discovered_conf or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form(user_input, None)

        if self.discovered_conf:
            user_input.update(self.discovered_conf)

        host = user_input[CONF_HOST]
        port = user_input.get(CONF_PORT)
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        use_ssl = user_input.get(CONF_SSL, DEFAULT_SSL)
        otp_code = user_input.get(CONF_OTP_CODE)

        if not port:
            if use_ssl is True:
                port = DEFAULT_PORT_SSL
            else:
                port = DEFAULT_PORT

        api = SynologyDSM(host, port, username, password, use_ssl)

        try:
            serial = await self.hass.async_add_executor_job(
                _login_and_fetch_syno_info, api, otp_code
            )
        except SynologyDSMLogin2SARequiredException:
            return await self.async_step_2sa(user_input)
        except SynologyDSMLogin2SAFailedException:
            errors[CONF_OTP_CODE] = "otp_failed"
            user_input[CONF_OTP_CODE] = None
            return await self.async_step_2sa(user_input, errors)
        except SynologyDSMLoginInvalidException as ex:
            _LOGGER.error(ex)
            errors[CONF_USERNAME] = "login"
        except SynologyDSMRequestException as ex:
            _LOGGER.error(ex)
            errors[CONF_HOST] = "connection"
        except SynologyDSMException as ex:
            _LOGGER.error(ex)
            errors["base"] = "unknown"
        except InvalidData:
            errors["base"] = "missing_data"

        if errors:
            return await self._show_setup_form(user_input, errors)

        # Check if already configured
        await self.async_set_unique_id(serial, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        config_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SSL: use_ssl,
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
        }
        if otp_code:
            config_data["device_token"] = api.device_token
        if user_input.get(CONF_DISKS):
            config_data[CONF_DISKS] = user_input[CONF_DISKS]
        if user_input.get(CONF_VOLUMES):
            config_data[CONF_VOLUMES] = user_input[CONF_VOLUMES]

        return self.async_create_entry(title=host, data=config_data)

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered synology_dsm."""
        parsed_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])
        friendly_name = (
            discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME].split("(", 1)[0].strip()
        )

        if self._host_already_configured(parsed_url.hostname):
            return self.async_abort(reason="already_configured")

        if ssdp.ATTR_UPNP_SERIAL in discovery_info:
            # Synology can broadcast on multiple IP addresses
            await self.async_set_unique_id(
                discovery_info[ssdp.ATTR_UPNP_SERIAL].upper()
            )
            self._abort_if_unique_id_configured()

        self.discovered_conf = {
            CONF_NAME: friendly_name,
            CONF_HOST: parsed_url.hostname,
        }
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = self.discovered_conf
        return await self.async_step_user()

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def async_step_link(self, user_input):
        """Link a config entry from discovery."""
        return await self.async_step_user(user_input)

    async def async_step_2sa(self, user_input, errors=None):
        """Enter 2SA code to anthenticate."""
        if not self.saved_user_input:
            self.saved_user_input = user_input

        if not user_input.get(CONF_OTP_CODE):
            return self.async_show_form(
                step_id="2sa",
                data_schema=vol.Schema({vol.Required(CONF_OTP_CODE): str}),
                errors=errors or {},
            )

        user_input = {**self.saved_user_input, **user_input}
        self.saved_user_input = {}

        return await self.async_step_user(user_input)

    def _host_already_configured(self, hostname):
        """See if we already have a host matching user input configured."""
        existing_hosts = {
            entry.data[CONF_HOST] for entry in self._async_current_entries()
        }
        return hostname in existing_hosts


def _login_and_fetch_syno_info(api, otp_code):
    """Login to the NAS and fetch basic data."""
    # These do i/o
    api.login(otp_code)
    utilisation = api.utilisation
    storage = api.storage

    if (
        api.information.serial is None
        or utilisation.cpu_user_load is None
        or storage.disks_ids is None
        or storage.volumes_ids is None
    ):
        raise InvalidData

    return api.information.serial


class InvalidData(exceptions.HomeAssistantError):
    """Error to indicate we get invalid data from the nas."""
