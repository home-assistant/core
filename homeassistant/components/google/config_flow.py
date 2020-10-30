"""Config flow to configure the AIS Google Calendar Service component."""

import logging

from oauth2client.client import (
    FlowExchangeError,
    OAuth2DeviceCodeError,
    OAuth2WebServerFlow,
)
from oauth2client.file import Storage

from homeassistant import config_entries
from homeassistant.components import ais_cloud
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME
from homeassistant.core import callback

from . import DOMAIN, TOKEN_FILE, do_setup

_LOGGER = logging.getLogger(__name__)
CONF_OAUTH_INFO = "oauth_info"
DEV_FLOW = None
OAUTH = None


@callback
def configured_google_calendar(hass):
    """Return a set of configured Google Calendar instances."""
    return {
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    }


class GoogleHomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Drive config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize google home configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        global OAUTH
        global DEV_FLOW
        errors = {}
        if user_input is not None:
            try:
                ais_dom = ais_cloud.AisCloudWS(self.hass)
                json_ws_resp = ais_dom.key("gcalendar_client_id")
                client_id = json_ws_resp["key"]
                json_ws_resp = ais_dom.key("gcalendar_secret")
                client_secret = json_ws_resp["key"]
                # oAuth
                OAUTH = OAuth2WebServerFlow(
                    client_id=client_id,
                    client_secret=client_secret,
                    scope="https://www.googleapis.com/auth/calendar",
                    redirect_uri="Home-Assistant.io",
                )
                DEV_FLOW = OAUTH.step1_get_device_and_user_codes()

                description_placeholders = {
                    "error_info": "",
                    "verification_url": DEV_FLOW.verification_url,
                    "user_code": DEV_FLOW.user_code,
                }

                return self.async_show_form(
                    step_id="oauth",
                    errors=None,
                    description_placeholders=description_placeholders,
                )

            except Exception as e:
                _LOGGER.error("Error calendar do_authentication: " + str(e))
                errors = {CONF_OAUTH_INFO: "oauth_error"}
                description_placeholders = {
                    "error_info": f"Error: {e}",
                    "verification_url": "",
                    "user_code": "",
                }
                return self.async_show_form(
                    step_id="oauth",
                    errors=errors,
                    description_placeholders=description_placeholders,
                )
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_oauth(self, user_input=None):
        """Handle a flow start."""
        global DEV_FLOW
        errors = {}
        description_placeholders = {"error_info": ""}
        if user_input is not None:
            try:
                credentials = OAUTH.step2_exchange(device_flow_info=DEV_FLOW)
                storage = Storage(self.hass.config.path(TOKEN_FILE))
                storage.put(credentials)
                do_setup(self.hass, None, None)

                return self.async_finish_flow(
                    title="AIS Google Calendar", data=user_input
                )
                # hass.components.persistent_notification.create(
                #     (
                #         f"OK, wszystko gotowe, twoje kalendarze zostały dodane do aplikacji, "
                #         f" konfiguracja kalendarzy przechowywana jest w pliku {YAML_DEVICES} "
                #     ),
                #     title=NOTIFICATION_TITLE,
                #     notification_id=NOTIFICATION_ID,
                # )
            except Exception as err:
                _LOGGER.error("Error calendar async_step_token: " + str(err))
                description_placeholders = {"error_info": f"Error: {err}"}
                return self.async_abort(
                    reason="abort_by_error",
                    description_placeholders=description_placeholders,
                )

        return self.async_show_form(
            step_id="oauth",
            errors=errors,
            description_placeholders=description_placeholders,
        )
