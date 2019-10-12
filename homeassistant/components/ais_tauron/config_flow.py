"""Config flow to configure Supla component."""

import voluptuous as vol
import datetime

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.util import slugify
import requests
import logging

from .const import (
    DOMAIN,
    CONF_URL_LOGIN,
    CONF_REQUEST_HEADERS,
    CONF_REQUEST_PAYLOAD_CHARTS,
    CONF_URL_CHARTS,
    CONF_METER_ID,
)

_LOGGER = logging.getLogger(__name__)


@callback
def configured_tauron_connectoin(hass):
    """Return a set of the configured supla hosts."""
    return set(
        (slugify(entry.data[CONF_SERVER]))
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class AisSuplaFlowHandler(config_entries.ConfigFlow):
    """AIS Supla config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize Supla configuration flow."""
        pass

    async def async_step_import(self, import_config):
        """Import the supla server as config entry."""
        _LOGGER.warning("Go to async_step_user")
        return await self.async_step_init(user_input=import_config)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        description_placeholders = {"error_info": ""}
        if user_input is not None:
            try:
                # Test connection
                payload_login = {
                    "username": user_input[CONF_USERNAME],
                    "password": user_input[CONF_PASSWORD],
                    "service": CONF_URL_LOGIN,
                }
                session = requests.session()
                response = session.request(
                    "POST",
                    CONF_URL_LOGIN,
                    data=payload_login,
                    headers=CONF_REQUEST_HEADERS,
                )
                session.request(
                    "POST",
                    CONF_URL_LOGIN,
                    data=payload_login,
                    headers=CONF_REQUEST_HEADERS,
                )

                if response.status_code != 200:
                    _LOGGER.warning(
                        "Invalid status_code from TAURON: %s (%s)", response.status_code
                    )
                    errors = {CONF_METER_ID: "server_no_connection"}
                    description_placeholders = {"error_info": str(response)}

                else:
                    """Finish config flow"""
                    days_before = 2
                    config_date = datetime.datetime.now() - datetime.timedelta(
                        days_before
                    )
                    payload = {
                        "dane[chartDay]": config_date.strftime("%d.%m.%Y"),
                        "dane[paramType]": "day",
                        "dane[smartNr]": user_input[CONF_METER_ID],
                        "dane[chartType]": 1,
                    }
                    response = session.request(
                        "POST",
                        CONF_URL_CHARTS,
                        data={**CONF_REQUEST_PAYLOAD_CHARTS, **payload},
                        headers=CONF_REQUEST_HEADERS,
                    )
                    json_data = response.json()
                    zones = json_data["dane"]["zone"]
                    _LOGGER.info("TAURON zones %s", zones)
                    return self.async_create_entry(title="AIS TAURON", data=user_input)
            except Exception as e:
                errors = {CONF_METER_ID: "server_no_connection"}
                description_placeholders = {"error_info": str(e)}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required("energy_meter_id"): str,
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )
