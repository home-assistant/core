import logging

import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)


class AisNbpConfigFlow(config_entries.ConfigFlow, domain="ais_nbp"):
    """przepływu konfiguracji w integracji."""

    async def async_step_user(self, user_input=None):
        """Uruchomienie konfiguracji przez użytkownika"""
        # przejście do kroku potwierdzenia dodania integracji
        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(self, user_input=None):
        """Obsługa kroku potwierdzenia przez użytkownika."""
        if user_input is not None:
            # wybór walut
            options = {
                vol.Optional("currency"): cv.multi_select(
                    {
                        "CHF": "Frank szwajcarski ",
                        "EUR": "Euro",
                        "GBP": "Funt szterling",
                        "USD": "Dolar amerykańsk",
                    }
                )
            }
            return self.async_show_form(
                step_id="settings", data_schema=vol.Schema(options)
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_settings(self, user_input=None):
        """Krok wyboru walut do śledzenia"""
        if user_input is not None:
            # Zakończenie i zapis konfiguracji
            return self.async_create_entry(
                title="Śledzenie ceny złota i kursów walut", data=user_input
            )

        return self.async_show_form(step_id="confirm")
