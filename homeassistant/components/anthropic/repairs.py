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
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .config_flow import get_model_list
from .const import (
    CONF_CHAT_MODEL,
    DATA_REPAIR_DEFER_RELOAD,
    DEFAULT,
    DEPRECATED_MODELS,
    DOMAIN,
)

if TYPE_CHECKING:
    from . import AnthropicConfigEntry


class ModelDeprecatedRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    _subentry_iter: Iterator[tuple[str, str]] | None
    _current_entry_id: str | None
    _current_subentry_id: str | None
    _reload_pending: set[str]
    _pending_updates: dict[str, dict[str, str]]

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._subentry_iter = None
        self._current_entry_id = None
        self._current_subentry_id = None
        self._reload_pending = set()
        self._pending_updates = {}

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        previous_entry_id: str | None = None
        if user_input is not None:
            previous_entry_id = self._async_update_current_subentry(user_input)
            self._clear_current_target()

        target = await self._async_next_target()
        next_entry_id = target[0].entry_id if target else None
        if previous_entry_id and previous_entry_id != next_entry_id:
            await self._async_apply_pending_updates(previous_entry_id)
        if target is None:
            await self._async_apply_all_pending_updates()
            return self.async_create_entry(data={})

        entry, subentry, model = target
        client = entry.runtime_data
        model_list = [
            model_option
            for model_option in await get_model_list(client)
            if not model_option["value"].startswith(tuple(DEPRECATED_MODELS))
        ]

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

            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue

            subentry = entry.subentries.get(subentry_id)
            if subentry is None:
                continue

            model = self._pending_model(entry_id, subentry_id)
            if model is None:
                model = subentry.data.get(CONF_CHAT_MODEL)
            if not model or not model.startswith(tuple(DEPRECATED_MODELS)):
                continue

            self._current_entry_id = entry_id
            self._current_subentry_id = subentry_id
            return entry, subentry, model

    def _async_update_current_subentry(self, user_input: dict[str, str]) -> str | None:
        """Update the currently selected subentry."""
        if not self._current_entry_id or not self._current_subentry_id:
            return None

        entry = self.hass.config_entries.async_get_entry(self._current_entry_id)
        if entry is None:
            return None

        subentry = entry.subentries.get(self._current_subentry_id)
        if subentry is None:
            return None

        updated_data = {
            **subentry.data,
            CONF_CHAT_MODEL: user_input[CONF_CHAT_MODEL],
        }
        if updated_data == subentry.data:
            return entry.entry_id
        self._queue_pending_update(
            entry.entry_id,
            subentry.subentry_id,
            updated_data[CONF_CHAT_MODEL],
        )
        return entry.entry_id

    def _clear_current_target(self) -> None:
        """Clear current target tracking."""
        self._current_entry_id = None
        self._current_subentry_id = None

    def _format_subentry_type(self, subentry_type: str) -> str:
        """Return a user-friendly subentry type label."""
        if subentry_type == "conversation":
            return "Conversation agent"
        if subentry_type in ("ai_task", "ai_task_data"):
            return "AI task"
        return subentry_type

    def _queue_pending_update(
        self, entry_id: str, subentry_id: str, model: str
    ) -> None:
        """Store a pending model update for a subentry."""
        self._pending_updates.setdefault(entry_id, {})[subentry_id] = model

    def _pending_model(self, entry_id: str, subentry_id: str) -> str | None:
        """Return a pending model update if one exists."""
        return self._pending_updates.get(entry_id, {}).get(subentry_id)

    def _mark_entry_for_reload(self, entry_id: str) -> None:
        """Prevent reload until repairs are complete for the entry."""
        self._reload_pending.add(entry_id)
        defer_reload_entries: set[str] = self.hass.data.setdefault(
            DOMAIN, {}
        ).setdefault(DATA_REPAIR_DEFER_RELOAD, set())
        defer_reload_entries.add(entry_id)

    async def _async_reload_entry(self, entry_id: str) -> None:
        """Reload an entry once all repairs are completed."""
        if entry_id not in self._reload_pending:
            return

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.state is not ConfigEntryState.LOADED:
            self._clear_defer_reload(entry_id)
            self._reload_pending.discard(entry_id)
            return

        if entry is not None:
            await self.hass.config_entries.async_reload(entry_id)

        self._clear_defer_reload(entry_id)
        self._reload_pending.discard(entry_id)

    def _clear_defer_reload(self, entry_id: str) -> None:
        """Remove entry from the deferred reload set."""
        defer_reload_entries: set[str] = self.hass.data.setdefault(
            DOMAIN, {}
        ).setdefault(DATA_REPAIR_DEFER_RELOAD, set())
        defer_reload_entries.discard(entry_id)

    async def _async_apply_pending_updates(self, entry_id: str) -> None:
        """Apply pending subentry updates for a single entry."""
        updates = self._pending_updates.pop(entry_id, None)
        if not updates:
            return

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            return

        changed = False
        for subentry_id, model in updates.items():
            subentry = entry.subentries.get(subentry_id)
            if subentry is None:
                continue

            updated_data = {
                **subentry.data,
                CONF_CHAT_MODEL: model,
            }
            if updated_data == subentry.data:
                continue

            if not changed:
                self._mark_entry_for_reload(entry_id)
                changed = True

            self.hass.config_entries.async_update_subentry(
                entry,
                subentry,
                data=updated_data,
            )

        if not changed:
            return

        await self._async_reload_entry(entry_id)

    async def _async_apply_all_pending_updates(self) -> None:
        """Apply all pending updates across entries."""
        for entry_id in list(self._pending_updates):
            await self._async_apply_pending_updates(entry_id)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == "model_deprecated":
        return ModelDeprecatedRepairFlow()
    raise HomeAssistantError("Unknown issue ID")
