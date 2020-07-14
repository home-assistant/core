"""Config flow for Smappee."""
import logging

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (  # pylint: disable=unused-import
    CONF_HOSTNAME,
    CONF_SERIALNUMBER,
    CONF_TITLE,
    DOMAIN,
)

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

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""
        if discovery_info is None:
            return self.async_abort(reason="connection_error")

        if not discovery_info[CONF_HOSTNAME].startswith("Smappee1"):
            # We currently only support Energy and Solar models (legacy)
            return self.async_abort(reason="invalid_mdns")

        # pylint: E1101: Instance of 'SmappeeFlowHandler' has no 'context' member (no-member)
        self.context = {"source": "zeroconf"}

        self.context.update(
            {
                CONF_HOSTNAME: discovery_info[CONF_HOSTNAME],
                CONF_TITLE: discovery_info[CONF_HOSTNAME].replace(".local.", ""),
                CONF_IP_ADDRESS: discovery_info["host"],
                CONF_SERIALNUMBER: discovery_info[CONF_HOSTNAME]
                .replace(".local.", "")
                .replace("Smappee", ""),
            }
        )

        # Prepare configuration flow
        return await self._handle_config_flow(discovery_info, True)

    async def async_step_zeroconf_confirm(self, discovery_info=None):
        """Handle a flow initiated by zeroconf."""
        return await self._handle_config_flow(discovery_info)

    async def _handle_config_flow(self, discovery_info=None, prepare=False):
        """Config flow handler for discovered Smappee monitors."""
        if discovery_info is None and not prepare:
            return self._show_confirm_dialog()

        discovery_info[CONF_HOSTNAME] = self.context.get(CONF_HOSTNAME)
        discovery_info[CONF_TITLE] = self.context.get(CONF_TITLE)
        discovery_info[CONF_IP_ADDRESS] = self.context.get(CONF_IP_ADDRESS)
        discovery_info[CONF_SERIALNUMBER] = self.context.get(CONF_SERIALNUMBER)

        # Check if already configured
        await self.async_set_unique_id(discovery_info[CONF_HOSTNAME])
        self._abort_if_unique_id_configured(
            updates={CONF_HOSTNAME: discovery_info[CONF_HOSTNAME]}
        )

        if prepare:
            return await self.async_step_zeroconf_confirm()

        return self.async_create_entry(
            title=discovery_info[CONF_TITLE],
            data={
                CONF_HOSTNAME: discovery_info[CONF_HOSTNAME],
                CONF_IP_ADDRESS: discovery_info[CONF_IP_ADDRESS],
                CONF_SERIALNUMBER: discovery_info[CONF_SERIALNUMBER],
            },
        )

    def _show_confirm_dialog(self, errors=None):
        """Show the confirm dialog to the user."""
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self.context.get(CONF_TITLE)},
            errors=errors or {},
        )
