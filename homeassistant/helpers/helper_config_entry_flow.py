"""Helpers for data entry flows for helper config entries."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, FlowResult


class HelperCommonFlowHandler:
    """Handle a config or options flow for helper."""

    def __init__(
        self,
        handler: HelperConfigFlowHandler,
        config_entry: config_entries.ConfigEntry | None,
    ) -> None:
        """Initialize a common handler."""
        self._handler = handler
        self._options = dict(config_entry.options) if config_entry is not None else {}

    async def async_step(self, _user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a step."""
        errors = None
        step_id = (
            self._handler.cur_step["step_id"] if self._handler.cur_step else "init"
        )
        if _user_input is not None:
            errors = {}
            try:
                user_input = await self._handler.async_validate_input(
                    self._handler.hass, step_id, _user_input
                )
            except vol.Invalid as exc:
                errors["base"] = str(exc)
            else:
                if (
                    next_step_id := self._handler.async_next_step(step_id, user_input)
                ) is None:
                    title = self._handler.async_config_entry_title(user_input)
                    return self._handler.async_create_entry(
                        title=title, data=user_input
                    )
                return self._handler.async_show_form(
                    step_id=next_step_id, data_schema=self._handler.steps[next_step_id]
                )

        return self._handler.async_show_form(
            step_id=step_id, data_schema=self._handler.steps[step_id], errors=errors
        )


class HelperConfigFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow for helper integrations."""

    steps: dict[str, vol.Schema]

    VERSION = 1

    # pylint: disable-next=arguments-differ
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)

        for step in cls.steps:
            setattr(cls, f"async_step_{step}", cls.async_step)

    def __init__(self) -> None:
        """Initialize config flow."""
        self._common_handler = HelperCommonFlowHandler(self, None)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step()

    async def async_step(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a step."""
        result = await self._common_handler.async_step(user_input)
        if result["type"] == RESULT_TYPE_CREATE_ENTRY:
            result["options"] = result["data"]
            result["data"] = {}
        return result

    # pylint: disable-next=no-self-use
    @abstractmethod
    def async_config_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return config entry title."""
        return ""

    # pylint: disable-next=no-self-use
    def async_next_step(self, step_id: str, user_input: dict[str, Any]) -> str | None:
        """Return next step_id, or None to finish the flow."""
        return None

    # pylint: disable-next=no-self-use
    async def async_validate_input(
        self, hass: HomeAssistant, step_id: str, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate user input."""
        return user_input
