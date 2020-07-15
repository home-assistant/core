"""Config flow for Smappee."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import CONF_HOSTNAME, CONF_SERIALNUMBER, CONF_TITLE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmappeeFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Smappee OAuth2 authentication."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self._handle_config_flow(user_input)

    async def async_step_zeroconf(self, user_input):
        """Handle zeroconf discovery."""
        if user_input is None:
            return self.async_abort(reason="connection_error")

        if not user_input[CONF_HOSTNAME].startswith("Smappee1"):
            # We currently only support Energy and Solar models (legacy)
            return self.async_abort(reason="invalid_mdns")

        self.context.update(
            {
                CONF_HOSTNAME: user_input[CONF_HOSTNAME],
                CONF_TITLE: user_input[CONF_HOSTNAME].replace(".local.", ""),
                CONF_IP_ADDRESS: user_input["host"],
                CONF_SERIALNUMBER: user_input[CONF_HOSTNAME]
                .replace(".local.", "")
                .replace("Smappee", ""),
            }
        )

        # Prepare configuration flow
        return await self._handle_config_flow(user_input, True)

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Handle a flow initiated by zeroconf."""
        return await self._handle_config_flow(user_input)

    async def _handle_config_flow(self, user_input=None, prepare=False):
        """Config flow handler for Smappee."""
        source = self.context.get("source")

        # Show LOCAL/CLOUD option or prepare zeroconf discovery flow
        if user_input is None and not prepare:
            if source == SOURCE_ZEROCONF:
                return self._show_zeroconf_confirm_dialog()

            # Show environment form with CLOUD or LOCAL option
            return self._show_setup_form(step="environment")

        # Environment chosen, request additional host information for LOCAL or OAuth2 flow for CLOUD
        if user_input is not None and "environment" in user_input:
            if user_input["environment"] == "LOCAL":
                self.context.update({"environment": "LOCAL"})
                return self._show_setup_form(step="host")
            else:
                # Use configuration.yaml CLOUD setup
                self.context.update({"environment": "CLOUD"})
                return await self.async_step_pick_implementation()

        if source == SOURCE_ZEROCONF:
            user_input[CONF_HOSTNAME] = self.context.get(CONF_HOSTNAME)
            user_input[CONF_TITLE] = self.context.get(CONF_TITLE)
            user_input[CONF_IP_ADDRESS] = self.context.get(CONF_IP_ADDRESS)
            user_input[CONF_SERIALNUMBER] = self.context.get(CONF_SERIALNUMBER)
        else:
            user_input[CONF_IP_ADDRESS] = user_input["host"]

        if user_input.get(CONF_IP_ADDRESS) is not None or not prepare:
            try:
                smappee_api = api.api.SmappeeLocalApi(ip=user_input[CONF_IP_ADDRESS])
                await self.hass.async_add_executor_job(smappee_api.logon)

                # LOCAL setup
                if not source == SOURCE_ZEROCONF:
                    for config_item in smappee_api.load_advanced_config():
                        if config_item["key"] == "mdnsHostName":
                            if not config_item["value"].startswith("Smappee1"):
                                # We currently only support Energy and Solar models (legacy)
                                return self.async_abort(reason="invalid_mdns")
                            user_input[CONF_HOSTNAME] = f'{config_item["value"]}.local'
                            user_input[CONF_TITLE] = config_item["value"]
                            user_input[CONF_SERIALNUMBER] = config_item[
                                "value"
                            ].replace("Smappee", "")
            except Exception:
                return self.async_abort(reason="connection_error")

        # Check if already configured
        await self.async_set_unique_id(user_input[CONF_TITLE])
        self._abort_if_unique_id_configured()

        if prepare:
            return await self.async_step_zeroconf_confirm()

        return self.async_create_entry(
            title=user_input[CONF_TITLE],
            data={
                CONF_HOSTNAME: user_input[CONF_HOSTNAME],
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                CONF_SERIALNUMBER: user_input[CONF_SERIALNUMBER],
            },
        )

    def _show_setup_form(self, step, errors=None):
        """Show the environment form to the user."""
        if step == "environment":
            data_schema = vol.Schema(
                {
                    vol.Required("environment", default="CLOUD"): vol.In(
                        ["CLOUD", "LOCAL"]
                    )
                }
            )
        elif step == "host":
            data_schema = vol.Schema({vol.Required(CONF_HOST): str})

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors or {},
        )

    def _show_zeroconf_confirm_dialog(self, errors=None):
        """Show the confirm dialog to the user."""
        serialnumber = self.context.get(CONF_SERIALNUMBER)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"serialnumber": serialnumber},
            errors=errors or {},
        )
