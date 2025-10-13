"""Config flow for Generic cover."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import switch
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_DURATION,
    CONF_SWITCH_CLOSE,
    CONF_SWITCH_OPEN,
    CONF_TILT_DURATION,
    DOMAIN,
)
from .cover import (
    ATTR_DURATION,
    ATTR_SWITCH_CLOSE_ENTITY_ID,
    ATTR_SWITCH_OPEN_ENTITY_ID,
    ATTR_TILT_DURATION,
)

_LOGGER = logging.getLogger(__name__)


class GenericCoverConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Generic Cover."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            errors = _validate_user_input(user_input)
            if not errors:
                # Set unique ID based on the switch entities used
                unique_id = (
                    f"{user_input[CONF_SWITCH_OPEN]}_{user_input[CONF_SWITCH_CLOSE]}"
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(CONF_SWITCH_OPEN): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=switch.DOMAIN)
                    ),
                    vol.Required(CONF_SWITCH_CLOSE): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=switch.DOMAIN)
                    ),
                    vol.Optional(CONF_DURATION): selector.DurationSelector(
                        selector.DurationSelectorConfig(
                            allow_negative=False,
                            enable_day=False,
                            enable_millisecond=True,
                        ),
                    ),
                    vol.Optional(CONF_TILT_DURATION): selector.DurationSelector(
                        selector.DurationSelectorConfig(
                            allow_negative=False,
                            enable_day=False,
                            enable_millisecond=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GenericCoverOptionsFlowHandler:
        """Get the options flow for this handler."""
        return GenericCoverOptionsFlowHandler()


class GenericCoverOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Generic Cover."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = None

        if user_input is not None:
            errors = _validate_user_input(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        defaults = {
            CONF_SWITCH_OPEN: self.config_entry.data[CONF_SWITCH_OPEN],
            CONF_SWITCH_CLOSE: self.config_entry.data[CONF_SWITCH_CLOSE],
            CONF_DURATION: self.config_entry.data.get(CONF_DURATION),
            CONF_TILT_DURATION: self.config_entry.data.get(CONF_TILT_DURATION),
        }

        entity_registry = er.async_get(self.hass)
        entity_entry = entity_registry.async_get_entity_id(
            domain="cover",
            platform="generic_cover",
            unique_id=self.config_entry.entry_id,  # Use the entry_id as the unique_id
        )

        if entity_entry:
            last_state = self.hass.states.get(entity_entry)
        else:
            last_state = None

        if last_state is not None:
            defaults = {
                CONF_SWITCH_OPEN: last_state.attributes.get(ATTR_SWITCH_OPEN_ENTITY_ID),
                CONF_SWITCH_CLOSE: last_state.attributes.get(
                    ATTR_SWITCH_CLOSE_ENTITY_ID
                ),
                CONF_DURATION: _parse_duration(
                    last_state.attributes.get(ATTR_DURATION)
                ),
                CONF_TILT_DURATION: _parse_duration(
                    last_state.attributes.get(ATTR_TILT_DURATION)
                ),
            }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SWITCH_OPEN,
                        default=defaults.get(CONF_SWITCH_OPEN),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=switch.DOMAIN)
                    ),
                    vol.Required(
                        CONF_SWITCH_CLOSE,
                        default=defaults.get(CONF_SWITCH_CLOSE),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=switch.DOMAIN)
                    ),
                    vol.Required(
                        CONF_DURATION, default=defaults.get(CONF_DURATION)
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(
                            allow_negative=False,
                            enable_day=False,
                            enable_millisecond=True,
                        ),
                    ),
                    vol.Required(
                        CONF_TILT_DURATION,
                        default=defaults.get(CONF_TILT_DURATION),
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(
                            allow_negative=False,
                            enable_day=False,
                            enable_millisecond=True,
                        )
                    ),
                }
            ),
            errors=errors,
        )


def _validate_user_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate the user input."""
    errors = {}
    # Ensure that the duration is greater than 0
    if CONF_DURATION in user_input:
        duration = timedelta(**(user_input[CONF_DURATION]))
        if duration == timedelta(0):
            errors[CONF_DURATION] = "invalid_duration"
    # Ensure that the tilt duration is greater than 0
    if CONF_TILT_DURATION in user_input:
        tilt_duration = timedelta(**(user_input[CONF_TILT_DURATION]))
        if tilt_duration == timedelta(0):
            errors[CONF_TILT_DURATION] = "invalid_tilt_duration"
    # Ensure switches are different
    if (
        user_input.get(CONF_SWITCH_OPEN)
        and user_input.get(CONF_SWITCH_CLOSE)
        and user_input[CONF_SWITCH_OPEN] == user_input[CONF_SWITCH_CLOSE]
    ):
        errors["base"] = "same_switch"
    return errors


def _parse_duration(duration_str: str | None) -> dict[str, int] | None:
    """Parse duration string to dict."""
    if not duration_str:
        return None
    try:
        # Try parsing with milliseconds
        dt = datetime.strptime(duration_str, "%H:%M:%S.%f")
    except ValueError:
        try:
            # Fallback to parsing without milliseconds
            dt = datetime.strptime(duration_str, "%H:%M:%S")
        except ValueError:
            return None
    return {
        "hours": dt.hour,
        "minutes": dt.minute,
        "seconds": dt.second,
        "milliseconds": dt.microsecond // 1000,
    }
