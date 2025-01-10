"""Config flow for Strip Controller integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_NUMBER_OF_SECTIONS,
    CONF_SECTION_END,
    CONF_SECTION_START,
    CONF_SECTIONS,
    DOMAIN,
)
from .scrpi.sc_rpi import ScRpiClient

_LOGGER = logging.getLogger(__name__)

# TOD: validate connection at first step so the user don't need to pass all steps to validate ip and port
# TOD: Load section (also with their colors) configuration from file in ConfigFlow so the user don't need to reconfigure the same sections twice. Loading sections from the generic configuration.yml of Home Assistant is enough


def validate_section(section: tuple[int, int]):
    """Validate section start and end."""
    if section[0] > section[1] or section[0] < 0 or section[1] < 0:
        raise InvalidSection


class ConfigFlowResult(FlowResult, total=False):
    """Typed result dict for config flow."""

    minor_version: int
    options: Mapping[str, Any]
    version: int


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Strip Controller."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the strip_controller ConfigFlow."""
        self._errors: dict[str, Any] = {}
        self._current_step: int = 0
        self._number_of_led: int
        self._device_name: str
        self._device_url: str | None = None
        self._number_of_sections: int
        self._sections: list[tuple[int, int]] = []

    async def async_step_section(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

                data = {
                    CONF_URL: self._device_url,
                    CONF_NAME: self._device_name,
                    CONF_SECTIONS: self._sections,
                }
                return self.async_create_entry(title=self._device_name, data=data)

        # step_id defines which method to call
        return self.async_show_form(
            step_id="section",
            data_schema=self._get_data_schema(),
            errors=self._errors,
            last_step=self._is_last_step(),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # TOD: device duplication should be check by MAC address or get IP associated to a hostname in order to raise AbortFlow("already_configured") in case of duplication
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

            await self._async_get_device(user_input[CONF_URL])

            self._number_of_sections = user_input[CONF_NUMBER_OF_SECTIONS]
            self._device_name = user_input[CONF_NAME]
            self._device_url = user_input[CONF_URL]
            self._number_of_led = await self._get_number_of_led()
            return self._next_step()

        # step_id defines which method to call
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_data_schema(),
            errors={},
            last_step=False,
        )

    async def _async_get_device(self, url: str):
        """Get device information from WLED device.

        Based in `_async_get_device` from homeassistant/components/wled/config_flow.py

        """
        # TOD: CONTINUE implementing "update" method in ScRpiClient (fix "status" command in sc-rpi if necessary)
        # TOD: then extract data in async_step_user, for example number of leds, from recently obtained device
        # Registering a callback like this await self.wled.listen(callback=self.async_set_updated_data) in _use_websocket method from homeassistant/components/wled/coordinator.py,
        # data will be updated asynchronously instead of polling it (see https://developers.home-assistant.io/docs/integration_fetching_data/),
        session = async_get_clientsession(self.hass)
        scrpi_client = ScRpiClient(url, session)
        return await scrpi_client.update()

    async def _get_number_of_led(self):
        # TOD: obtain number of led to set default section length with it (0 to number_of_led)
        return 300

    def _is_error(self):
        return self._errors.keys().__len__() > 0

    def _is_last_step(self):
        return self._current_step == self._number_of_sections

    def _next_step(self) -> ConfigFlowResult:
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
                vol.Required(CONF_URL, default=None): str,
                vol.Required(CONF_NUMBER_OF_SECTIONS, default=None): int,
            }
        )


class InvalidSection(HomeAssistantError):
    """Error to indicate there is invalid auth."""
