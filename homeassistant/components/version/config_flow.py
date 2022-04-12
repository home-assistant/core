"""Config flow for Version integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_SOURCE
from homeassistant.data_entry_flow import FlowResult

from .const import (
    ATTR_VERSION_SOURCE,
    CONF_BETA,
    CONF_BOARD,
    CONF_CHANNEL,
    CONF_IMAGE,
    CONF_VERSION_SOURCE,
    DEFAULT_BOARD,
    DEFAULT_CHANNEL,
    DEFAULT_CONFIGURATION,
    DEFAULT_IMAGE,
    DEFAULT_NAME_CURRENT,
    DOMAIN,
    STEP_USER,
    STEP_VERSION_SOURCE,
    VALID_BOARDS,
    VALID_CHANNELS,
    VALID_CONTAINER_IMAGES,
    VALID_IMAGES,
    VERSION_SOURCE_LOCAL,
    VERSION_SOURCE_MAP,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Version."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Version config flow."""
        self._entry_data: dict[str, Any] = DEFAULT_CONFIGURATION.copy()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial user step."""
        if user_input is None:
            self._entry_data = DEFAULT_CONFIGURATION.copy()
            return self.async_show_form(
                step_id=STEP_USER,
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_VERSION_SOURCE,
                            default=VERSION_SOURCE_LOCAL,
                        ): vol.In(VERSION_SOURCE_MAP.keys())
                    }
                ),
            )

        user_input[CONF_SOURCE] = VERSION_SOURCE_MAP[user_input[CONF_VERSION_SOURCE]]
        self._entry_data.update(user_input)

        if not self.show_advanced_options or user_input[CONF_SOURCE] in (
            "local",
            "haio",
        ):
            return self.async_create_entry(
                title=self._config_entry_name,
                data=self._entry_data,
            )

        return await self.async_step_version_source()

    async def async_step_version_source(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the version_source step."""
        if user_input is None:
            if self._entry_data[CONF_SOURCE] in (
                "supervisor",
                "container",
            ):
                data_schema = vol.Schema(
                    {
                        vol.Required(
                            CONF_CHANNEL, default=DEFAULT_CHANNEL.title()
                        ): vol.In(VALID_CHANNELS),
                    }
                )
                if self._entry_data[CONF_SOURCE] == "supervisor":
                    data_schema = data_schema.extend(
                        {
                            vol.Required(CONF_IMAGE, default=DEFAULT_IMAGE): vol.In(
                                VALID_IMAGES
                            ),
                            vol.Required(CONF_BOARD, default=DEFAULT_BOARD): vol.In(
                                VALID_BOARDS
                            ),
                        }
                    )
                else:
                    data_schema = data_schema.extend(
                        {
                            vol.Required(CONF_IMAGE, default=DEFAULT_IMAGE): vol.In(
                                VALID_CONTAINER_IMAGES
                            )
                        }
                    )
            else:
                data_schema = vol.Schema({vol.Required(CONF_BETA, default=False): bool})

            return self.async_show_form(
                step_id=STEP_VERSION_SOURCE,
                data_schema=data_schema,
                description_placeholders={
                    ATTR_VERSION_SOURCE: self._entry_data[CONF_VERSION_SOURCE]
                },
            )
        self._entry_data.update(user_input)
        self._entry_data[CONF_CHANNEL] = self._entry_data[CONF_CHANNEL].lower()

        return self.async_create_entry(
            title=self._config_entry_name, data=self._entry_data
        )

    @property
    def _config_entry_name(self) -> str:
        """Return the name of the config entry."""
        if self._entry_data[CONF_SOURCE] == "local":
            return DEFAULT_NAME_CURRENT

        name = self._entry_data[CONF_VERSION_SOURCE]

        if (channel := self._entry_data[CONF_CHANNEL]) != DEFAULT_CHANNEL:
            return f"{name} {channel.title()}"

        return name
