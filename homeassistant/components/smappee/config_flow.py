"""Config flow for Smappee."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import CONF_HOSTNAME, CONF_SERIALNUMBER, DOMAIN, ENV_CLOUD, ENV_LOCAL

_LOGGER = logging.getLogger(__name__)


class SmappeeFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config Smappee config flow."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""

        if not discovery_info[CONF_HOSTNAME].startswith("Smappee1"):
            # We currently only support Energy and Solar models (legacy)
            return self.async_abort(reason="invalid_mdns")

        serial_number = (
            discovery_info[CONF_HOSTNAME].replace(".local.", "").replace("Smappee", "")
        )

        # Check if already configured
        await self.async_set_unique_id(f"Smappee{serial_number}")
        self._abort_if_unique_id_configured()

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update(
            {CONF_IP_ADDRESS: discovery_info["host"], CONF_SERIALNUMBER: serial_number}
        )

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Confirm zeroconf flow."""
        errors = {}

        if user_input is None:
            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            serialnumber = self.context.get(CONF_SERIALNUMBER)
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"serialnumber": serialnumber},
                errors=errors,
            )

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        ip_address = self.context.get(CONF_IP_ADDRESS)
        serial_number = self.context.get(CONF_SERIALNUMBER)

        # Attempt to make a connection to the local device
        smappee_api = api.api.SmappeeLocalApi(ip=ip_address)
        logon = await self.hass.async_add_executor_job(smappee_api.logon)
        if logon is None:
            return self.async_abort(reason="connection_error")

        return self.async_create_entry(
            title=f"Smappee{serial_number}",
            data={CONF_IP_ADDRESS: ip_address, CONF_SERIALNUMBER: serial_number},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self.async_step_environment()

    async def async_step_environment(self, user_input=None):
        """Decide environment, cloud or local."""
        if user_input is None:
            return self.async_show_form(
                step_id="environment",
                data_schema=vol.Schema(
                    {
                        vol.Required("environment", default=ENV_CLOUD): vol.In(
                            [ENV_CLOUD, ENV_LOCAL]
                        )
                    }
                ),
                errors={},
            )

        # Environment chosen, request additional host information for LOCAL or OAuth2 flow for CLOUD
        # Ask for host detail
        if user_input["environment"] == ENV_LOCAL:
            return await self.async_step_local()

        # Use configuration.yaml CLOUD setup
        return await self.async_step_pick_implementation()

    async def async_step_local(self, user_input=None):
        """Handle local flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                errors={},
            )
        # In a LOCAL setup we still need to resolve the host to serial number
        ip_address = user_input["host"]
        smappee_api = api.api.SmappeeLocalApi(ip=ip_address)
        logon = await self.hass.async_add_executor_job(smappee_api.logon)
        if logon is None:
            return self.async_abort(reason="connection_error")

        advanced_config = await self.hass.async_add_executor_job(
            smappee_api.load_advanced_config
        )
        serial_number = None
        for config_item in advanced_config:
            if config_item["key"] == "mdnsHostName":
                serial_number = config_item["value"]

        if serial_number is None or not serial_number.startswith("Smappee1"):
            # We currently only support Energy and Solar models (legacy)
            return self.async_abort(reason="invalid_mdns")

        serial_number = serial_number.replace("Smappee", "")

        # Check if already configured
        await self.async_set_unique_id(
            f"Smappee{serial_number}", raise_on_progress=False
        )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Smappee{serial_number}",
            data={CONF_IP_ADDRESS: ip_address, CONF_SERIALNUMBER: serial_number},
        )
