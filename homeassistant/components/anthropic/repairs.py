"""Issue repair flow for Anthropic."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, cast

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .config_flow import get_model_list
from .const import CONF_CHAT_MODEL, DEFAULT, DEPRECATED_MODELS, DOMAIN

if TYPE_CHECKING:
    from . import AnthropicConfigEntry


class ModelDeprecatedRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    _subentry_iter: Iterator[tuple[str, str]] | None
    _current_entry_id: str | None
    _current_subentry_id: str | None
    _model_list_cache: dict[str, list[SelectOptionDict]] | None

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._subentry_iter = None
        self._current_entry_id = None
        self._current_subentry_id = None
        self._model_list_cache = None

    async def async_step_init(
        self, user_input: dict[str, str]
    ) -> data_entry_flow.FlowResult:
        """Handle the steps of a fix flow."""
        if user_input.get(CONF_CHAT_MODEL):
            self._async_update_current_subentry(user_input)

        target = await self._async_next_target()
        if target is None:
            return self.async_create_entry(data={})

        entry, subentry, model = target
        if self._model_list_cache is None:
            self._model_list_cache = {}
        if entry.entry_id in self._model_list_cache:
            model_list = self._model_list_cache[entry.entry_id]
        else:
            client = entry.runtime_data
            model_list = [
                model_option
                for model_option in await get_model_list(client)
                if not model_option["value"].startswith(tuple(DEPRECATED_MODELS))
            ]
            self._model_list_cache[entry.entry_id] = model_list

        if "opus" in model:
            suggested_model = "claude-opus-4-5"
        elif "haiku" in model:
            suggested_model = "claude-haiku-4-5"
        elif "sonnet" in model:
            suggested_model = "claude-sonnet-4-5"
        else:
            suggested_model = cast(str, DEFAULT[CONF_CHAT_MODEL])

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CHAT_MODEL,
                    default=suggested_model,
                ): SelectSelector(
                    SelectSelectorConfig(options=model_list, custom_value=True)
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "entry_name": entry.title,
                "model": model,
                "subentry_name": subentry.title,
                "subentry_type": self._format_subentry_type(subentry.subentry_type),
            },
        )

    def _iter_deprecated_subentries(self) -> Iterator[tuple[str, str]]:
        """Yield entry/subentry pairs that use deprecated models."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            for subentry in entry.subentries.values():
                model = subentry.data.get(CONF_CHAT_MODEL)
                if model and model.startswith(tuple(DEPRECATED_MODELS)):
                    yield entry.entry_id, subentry.subentry_id

    async def _async_next_target(
        self,
    ) -> tuple[AnthropicConfigEntry, ConfigSubentry, str] | None:
        """Return the next deprecated subentry target."""
        if self._subentry_iter is None:
            self._subentry_iter = self._iter_deprecated_subentries()

        while True:
            try:
                entry_id, subentry_id = next(self._subentry_iter)
            except StopIteration:
                return None

            # Verify that the entry/subentry still exists and the model is still
            # deprecated. This may have changed since we started the repair flow.
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue

            subentry = entry.subentries.get(subentry_id)
            if subentry is None:
                continue

            model = subentry.data.get(CONF_CHAT_MODEL)
            if not model or not model.startswith(tuple(DEPRECATED_MODELS)):
                continue

            self._current_entry_id = entry_id
            self._current_subentry_id = subentry_id
            return entry, subentry, model

    def _async_update_current_subentry(self, user_input: dict[str, str]) -> None:
        """Update the currently selected subentry."""
        if (
            self._current_entry_id is None
            or self._current_subentry_id is None
            or (
                entry := self.hass.config_entries.async_get_entry(
                    self._current_entry_id
                )
            )
            is None
            or (subentry := entry.subentries.get(self._current_subentry_id)) is None
        ):
            raise HomeAssistantError("Subentry not found")

        updated_data = {
            **subentry.data,
            CONF_CHAT_MODEL: user_input[CONF_CHAT_MODEL],
        }
        self.hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data=updated_data,
        )

    def _format_subentry_type(self, subentry_type: str) -> str:
        """Return a user-friendly subentry type label."""
        if subentry_type == "conversation":
            return "Conversation agent"
        if subentry_type in ("ai_task", "ai_task_data"):
            return "AI task"
        return subentry_type


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == "model_deprecated":
        return ModelDeprecatedRepairFlow()
    raise HomeAssistantError("Unknown issue ID")
