"""Config flow to connect with Home Assistant."""
import logging

from yarl import URL
import voluptuous as vol

from homeassistant import data_entry_flow, config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, TYPE_LOCAL, TYPE_OAUTH2


class AlmondFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Implementation of the Almond OAuth2 config flow."""

    DOMAIN = DOMAIN

    host = None
    hassio_discovery = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "profile user-read user-read-results user-exec-command"}

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        # Only allow 1 instance.
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")

        return await super().async_step_user(user_input)

    async def async_step_auth(self, user_input=None):
        """Handle authorize step."""
        result = await super().async_step_auth(user_input)

        if result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP:
            self.host = str(URL(result["url"]).with_path("me"))

        return result

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow.

        Ok to override if you want to fetch extra info or even add another step.
        """
        # pylint: disable=invalid-name
        self.CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
        data["type"] = TYPE_OAUTH2
        data["host"] = self.host
        return self.async_create_entry(title=self.flow_impl.name, data=data)

    async def async_step_import(self, user_input: dict = None) -> dict:
        """Import data."""
        # Only allow 1 instance.
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")

        # pylint: disable=invalid-name
        self.CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

        return self.async_create_entry(
            title="Configuration.yaml",
            data={"type": TYPE_LOCAL, "host": user_input["host"]},
        )

    async def async_step_hassio(self, user_input=None):
        """Receive a Hass.io discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")

        self.hassio_discovery = user_input

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input=None):
        """Confirm a Hass.io discovery."""
        data = self.hassio_discovery

        if user_input is not None:
            return self.async_create_entry(
                title=data["addon"],
                data={
                    "is_hassio": True,
                    "type": TYPE_LOCAL,
                    "host": f"http://{data['host']}:{data['port']}",
                },
            )

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": data["addon"]},
            data_schema=vol.Schema({}),
        )
