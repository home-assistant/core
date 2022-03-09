"""Helpers for data entry flows for helper config entries."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Mapping
import copy
from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, UnknownHandler


@dataclass
class HelperFlowStep:
    """Define a helper config or options flow step."""

    # Optional schema for requesting and validating user input. If schema validation
    # fails, the step will be retried. If the schema is None, no user input is requested.
    schema: vol.Schema | None

    # Optional function to identify next step.
    # The next_step function is called if the schema validates successfully or if no
    # schema is defined. The next_step function is passed the union of config entry
    # options and user input from previous steps.
    # If next_step returns None, the flow is ended with RESULT_TYPE_CREATE_ENTRY.
    next_step: Callable[[dict[str, Any]], str | None] = lambda _: None


class HelperCommonFlowHandler:
    """Handle a config or options flow for helper."""

    def __init__(
        self,
        handler: HelperConfigFlowHandler | HelperOptionsFlowHandler,
        flow: dict[str, HelperFlowStep],
        config_entry: config_entries.ConfigEntry | None,
    ) -> None:
        """Initialize a common handler."""
        self._flow = flow
        self._handler = handler
        self._options = dict(config_entry.options) if config_entry is not None else {}

    async def async_step(
        self, step_id: str, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a step."""
        next_step_id: str = step_id

        if user_input is not None:
            # User input was validated successfully, update options
            self._options.update(user_input)

        if self._flow[next_step_id].next_step and (
            user_input is not None or self._flow[next_step_id].schema is None
        ):
            # Get next step
            next_step_id_or_end_flow = self._flow[next_step_id].next_step(self._options)
            if next_step_id_or_end_flow is None:
                # Flow done, create entry or update config entry options
                return self._handler.async_create_entry(data=self._options)

            next_step_id = next_step_id_or_end_flow

        if (data_schema := self._flow[next_step_id].schema) and data_schema.schema:
            # Copy the schema, then set suggested field values to saved options
            schema = dict(data_schema.schema)
            for key in list(schema):
                if key in self._options and isinstance(key, vol.Marker):
                    # Copy the marker to not modify the flow schema
                    new_key = copy.copy(key)
                    new_key.description = {"suggested_value": self._options[key]}
                    val = schema.pop(key)
                    schema[new_key] = val
            data_schema = vol.Schema(schema)

        # Show form for next step
        return self._handler.async_show_form(
            step_id=next_step_id, data_schema=data_schema
        )


class HelperConfigFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow for helper integrations."""

    config_flow: dict[str, HelperFlowStep]
    options_flow: dict[str, HelperFlowStep] | None = None

    VERSION = 1

    # pylint: disable-next=arguments-differ
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Initialize a subclass."""
        super().__init_subclass__(**kwargs)

        @callback
        def _async_get_options_flow(
            config_entry: config_entries.ConfigEntry,
        ) -> config_entries.OptionsFlow:
            """Get the options flow for this handler."""
            if cls.options_flow is None:
                raise UnknownHandler

            return HelperOptionsFlowHandler(config_entry, cls.options_flow)

        # Create an async_get_options_flow method
        cls.async_get_options_flow = _async_get_options_flow  # type: ignore[assignment]

        # Create flow step methods for each step defined in the flow schema
        for step in cls.config_flow:
            setattr(cls, f"async_step_{step}", cls._async_step)

    def __init__(self) -> None:
        """Initialize config flow."""
        self._common_handler = HelperCommonFlowHandler(self, self.config_flow, None)

    @classmethod
    @callback
    def async_supports_options_flow(
        cls, config_entry: config_entries.ConfigEntry
    ) -> bool:
        """Return options flow support for this handler."""
        return cls.options_flow is not None

    async def _async_step(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a config flow step."""
        step_id = self.cur_step["step_id"] if self.cur_step else "user"
        result = await self._common_handler.async_step(step_id, user_input)

        return result

    # pylint: disable-next=no-self-use
    @abstractmethod
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title.

        The options parameter contains config entry options, which is the union of user
        input from the config flow steps.
        """

    @callback
    def async_create_entry(  # pylint: disable=arguments-differ
        self,
        data: Mapping[str, Any],
        **kwargs: Any,
    ) -> FlowResult:
        """Finish config flow and create a config entry."""
        return super().async_create_entry(
            data={}, options=data, title=self.async_config_entry_title(data), **kwargs
        )


class HelperOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for helper integrations."""

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        options_flow: dict[str, vol.Schema],
    ) -> None:
        """Initialize options flow."""
        self._common_handler = HelperCommonFlowHandler(self, options_flow, config_entry)
        self._config_entry = config_entry

        for step in options_flow:
            setattr(self, f"async_step_{step}", self._async_step)

    async def _async_step(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle an options flow step."""
        # pylint: disable-next=unsubscriptable-object # self.cur_step is a dict
        step_id = self.cur_step["step_id"] if self.cur_step else "init"
        return await self._common_handler.async_step(step_id, user_input)

    @callback
    def async_create_entry(  # pylint: disable=arguments-differ
        self,
        **kwargs: Any,
    ) -> FlowResult:
        """Finish config flow and create a config entry."""
        return super().async_create_entry(title="", **kwargs)
