"""Helpers for data entry flows for helper config entries."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Awaitable, Callable
import copy
import types
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import (
    RESULT_TYPE_CREATE_ENTRY,
    FlowResult,
    UnknownHandler,
)

from . import entity_registry as er


class HelperCommonFlowHandler:
    """Handle a config or options flow for helper."""

    def __init__(
        self,
        handler: HelperConfigFlowHandler | HelperOptionsFlowHandler,
        config_entry: config_entries.ConfigEntry | None,
    ) -> None:
        """Initialize a common handler."""
        self._handler = handler
        self._options = dict(config_entry.options) if config_entry is not None else {}

    async def async_step(
        self, step_id: str, _user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a step."""
        errors = None
        if _user_input is not None:
            errors = {}
            try:
                user_input = await self._handler.async_validate_input(
                    self._handler.hass, step_id, _user_input
                )
            except vol.Invalid as exc:
                errors["base"] = str(exc)
            else:
                self._options.update(user_input)
                if (
                    next_step_id := self._handler.async_next_step(step_id, user_input)
                ) is None:
                    title = self._handler.async_config_entry_title(user_input)
                    return self._handler.async_create_entry(
                        title=title, data=self._options
                    )
                return self._handler.async_show_form(
                    step_id=next_step_id, data_schema=self._handler.steps[next_step_id]
                )

        schema = dict(self._handler.steps[step_id].schema)
        for key in list(schema):
            if key in self._options and isinstance(key, vol.Marker):
                new_key = copy.copy(key)
                new_key.description = {"suggested_value": self._options[key]}
                val = schema.pop(key)
                schema[new_key] = val

        return self._handler.async_show_form(
            step_id=step_id, data_schema=vol.Schema(schema), errors=errors
        )


class HelperConfigFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow for helper integrations."""

    _config_entry: config_entries.ConfigEntry | None = None
    steps: dict[str, vol.Schema]

    VERSION = 1

    # pylint: disable-next=arguments-differ
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)

        @callback
        def _async_get_options_flow(
            config_entry: config_entries.ConfigEntry,
        ) -> config_entries.OptionsFlow:
            """Get the options flow for this handler."""
            if (
                cls.async_initial_options_step
                is HelperConfigFlowHandler.async_initial_options_step
            ):
                raise UnknownHandler

            return HelperOptionsFlowHandler(
                config_entry,
                cls.steps,
                cls.async_config_entry_title,
                cls.async_initial_options_step,
                cls.async_next_step,
                cls.async_validate_input,
            )

        # Create an async_get_options_flow method
        cls.async_get_options_flow = _async_get_options_flow  # type: ignore[assignment]
        # Create flow step methods for each step defined in the flow schema
        for step in cls.steps:
            setattr(cls, f"async_step_{step}", cls.async_step)

    def __init__(self) -> None:
        """Initialize config flow."""
        self._common_handler = HelperCommonFlowHandler(self, None)

    @classmethod
    @callback
    def async_supports_options_flow(
        cls, config_entry: config_entries.ConfigEntry
    ) -> bool:
        """Return options flow support for this handler."""
        return (
            cls.async_initial_options_step
            is not HelperConfigFlowHandler.async_initial_options_step
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step()

    async def async_step(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a step."""
        step_id = self.cur_step["step_id"] if self.cur_step else "init"
        result = await self._common_handler.async_step(step_id, user_input)
        if result["type"] == RESULT_TYPE_CREATE_ENTRY:
            result["options"] = result["data"]
            result["data"] = {}
        return result

    # pylint: disable-next=no-self-use
    @abstractmethod
    def async_config_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return config entry title."""

    # pylint: disable-next=no-self-use
    def async_next_step(self, step_id: str, user_input: dict[str, Any]) -> str | None:
        """Return next step_id, or None to finish the flow."""
        return None

    @staticmethod
    @callback
    def async_initial_options_step(
        config_entry: config_entries.ConfigEntry,
    ) -> str:
        """Return initial step_id of options flow."""
        raise UnknownHandler

    # pylint: disable-next=no-self-use
    async def async_validate_input(
        self, hass: HomeAssistant, step_id: str, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate user input."""
        return user_input


class HelperOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for helper integrations."""

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        steps: dict[str, vol.Schema],
        config_entry_title: Callable[[Any, dict[str, Any]], str],
        initial_step: Callable[[config_entries.ConfigEntry], str],
        next_step: Callable[[Any, str, dict[str, Any]], str | None],
        validate: Callable[
            [Any, HomeAssistant, str, dict[str, Any]], Awaitable[dict[str, Any]]
        ],
    ) -> None:
        """Initialize options flow."""
        self._common_handler = HelperCommonFlowHandler(self, config_entry)
        self._config_entry = config_entry
        self._initial_step = initial_step(config_entry)
        self.async_config_entry_title = types.MethodType(config_entry_title, self)
        self.async_next_step = types.MethodType(next_step, self)
        self.async_validate_input = types.MethodType(validate, self)
        self.steps = steps
        for step in self.steps:
            if step == "init":
                continue
            setattr(self, f"async_step_{step}", self.async_step)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step(user_input)

    async def async_step(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a step."""
        # pylint: disable-next=unsubscriptable-object # self.cur_step is a dict
        step_id = self.cur_step["step_id"] if self.cur_step else self._initial_step
        return await self._common_handler.async_step(step_id, user_input)


def async_own_entity_not_selected(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    config_entry: config_entries.ConfigEntry,
    platform: str,
    domain: str,
    selected_entities: list[str],
) -> dict[str, Any]:
    """Raise is config entry's own entity is included in selection."""
    registry = er.async_get(hass)
    entry_id = config_entry.entry_id
    entity_id = registry.async_get_entity_id(platform, domain, entry_id)

    if not entity_id:
        return user_input

    if entity_id in selected_entities:
        raise vol.Invalid("own_entity_not_allowed")

    entity_entry = registry.async_get(entity_id)
    if entity_entry and entity_entry.id in selected_entities:
        raise vol.Invalid("own_entity_not_allowed")

    return user_input
