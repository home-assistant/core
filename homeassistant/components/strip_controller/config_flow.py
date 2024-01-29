"""Config flow for Strip Controller integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_IP_ADDRESS,
    CONF_NUMBER_OF_SECTIONS,
    CONF_SECTION_END,
    CONF_SECTION_START,
    CONF_SECTIONS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# TOD: Set custom icon/logo upgrade HA version to 2024.x and set icon (more info: https://developers.home-assistant.io/blog/2024/01/19/icon-translations/)
# TOD: Create  OptionsFlow to edit sections (check homeassistant/components/met/config_flow.py).
# TOD: validate connection at first step so the user don't need to pass all steps to validate ip and port
# TOD: Load section (also with their colors) configuration from file in ConfigFlow so the user don't need to reconfigure the same sections twice. Loading sections from the generic configuration.yml of Home Assistant is enough
# TOD: Prevent setting the same device twice (allow only one entity ).


def validate_section(section: tuple[int, int]):
    """Validate section start and end."""
    if section[0] > section[1] or section[0] < 0 or section[1] < 0:
        raise InvalidSection


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Strip Controller."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the strip_controller ConfigFlow."""
        self._errors: dict[str, Any] = {}
        self._current_step: int = 0
        self._number_of_led: int
        self._device_name: str
        self._number_of_sections: int
        self._sections: list[tuple[int, int]] = []

    async def async_step_section(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle configuration of each section in the strip."""
        if user_input is not None:
            try:
                section = (user_input[CONF_SECTION_START], user_input[CONF_SECTION_END])
                validate_section(section)
            except InvalidSection:
                self._errors["base"] = "invalid_section"
            else:
                self._sections.append(
                    (user_input[CONF_SECTION_START], user_input[CONF_SECTION_END])
                )

                if not self._is_last_step():
                    return self._next_step()

                data = {CONF_SECTIONS: self._sections, CONF_NAME: self._device_name}
                return self.async_create_entry(title=self._device_name, data=data)

        return self.async_show_form(
            step_id="section",
            data_schema=self._get_data_schema(),
            errors=self._errors,
            last_step=self._is_last_step(),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._number_of_sections = user_input[CONF_NUMBER_OF_SECTIONS]
            self._device_name = user_input[CONF_NAME]
            self._number_of_led = await self._get_number_of_led()
            return self._next_step()

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_data_schema(),
            errors={},
            last_step=False,
        )

        # TOD hacer que desde acá se creen todas las secciones, cada step crea 1 seccion

    async def _get_number_of_led(self):
        # TOD: obtain number of led to set default section length with it (0 to number_of_led)
        return 300

    def _is_error(self):
        return self._errors.keys().__len__() > 0

    def _is_last_step(self):
        return self._current_step == self._number_of_sections

    def _next_step(self) -> FlowResult:
        self._current_step = self._current_step + 1
        return self.async_show_form(
            step_id="section",
            data_schema=self._get_data_schema(),
            errors=self._errors,
            last_step=self._is_last_step(),
        )

    def _get_data_schema(self) -> vol.Schema:
        """Get a schema dynamically generating default values."""
        if self._current_step > 0:
            default_start = (
                0
                if self._current_step == 1
                else (self._sections[-1][1] + 1 if self._current_step >= 1 else 0)
            )
            default_end = self._number_of_led - 1
            return vol.Schema(
                {
                    vol.Required(CONF_SECTION_START, default=default_start): int,
                    vol.Required(CONF_SECTION_END, default=default_end): int,
                }
            )
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=None): str,
                vol.Required(CONF_IP_ADDRESS, default=None): str,
                vol.Required(CONF_PORT, default=None): int,
                vol.Required(CONF_NUMBER_OF_SECTIONS, default=None): int,
            }
        )


class InvalidSection(HomeAssistantError):
    """Error to indicate there is invalid auth."""
