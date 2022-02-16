from base64 import b64encode
import json
import logging

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client

_LOGGER = logging.getLogger(__name__)


class AisNbpConfigFlow(config_entries.ConfigFlow, domain="ais_easy"):
    """przepływu konfiguracji w integracji."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Uruchomienie konfiguracji przez użytkownika"""
        # przejście do kroku potwierdzenia dodania integracji
        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(self, user_input=None):
        """Obsługa kroku potwierdzenia przez użytkownika."""
        if user_input is not None:
            # token i host
            return self.async_show_form(
                step_id="settings",
                data_schema=vol.Schema({"host": str, "user": str, "pass": str}),
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_settings(self, user_input=None):
        """Krok parametry połączenie z plc"""
        if user_input is not None:
            # check the connection to PLC
            try:
                with async_timeout.timeout(15):
                    web_session = aiohttp_client.async_get_clientsession(self.hass)
                    encoded_credentials = b64encode(
                        bytes(
                            f"{user_input['user']}:{user_input['pass']}",
                            encoding="ascii",
                        )
                    ).decode("ascii")

                    header = {
                        "Authorization": "Basic %s" % encoded_credentials,
                        "Content-Type": "application/json",
                    }
                    url = "http://" + user_input["host"] + "/api/get/data?elm=STATE"

                    ws_resp = await web_session.get(url, headers=header)
                    info = await ws_resp.text()
                    info_json = json.loads(info)
                    # Zakończenie i zapis konfiguracji
                    return self.async_create_entry(title="Easy PLC", data=user_input)

            except Exception as e:
                _LOGGER.error("Ask Easy error: " + str(e))
                # Informacja o błędzie
                errors = {"host": "connection_error"}
                return self.async_show_form(
                    step_id="settings",
                    data_schema=vol.Schema({"host": str, "user": str, "pass": str}),
                    errors=errors,
                )

        return self.async_show_form(step_id="confirm")
