import logging

import voluptuous as vol

from homeassistant import config_entries

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
                step_id="settings", data_schema=vol.Schema({"host": str, "token": str})
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_settings(self, user_input=None):
        """Krok wyboru walut do śledzenia"""
        if user_input is not None:
            # Zakończenie i zapis konfiguracji
            return self.async_create_entry(title="Easy PLC", data=user_input)

        return self.async_show_form(step_id="confirm")
