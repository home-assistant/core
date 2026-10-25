"""Issue repair flow for Anthropic."""

from collections.abc import Iterator
from typing import TYPE_CHECKING, cast

import anthropic
from anthropic.resources.messages.messages import DEPRECATED_MODELS
import probatio

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_CHAT_MODEL, DOMAIN
from .coordinator import model_alias
from .model_options import reconcile_model_options

if TYPE_CHECKING:
    from .coordinator import AnthropicConfigEntry


class ModelDeprecatedRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    _subentry_iter: Iterator[tuple[str, str]] | None
    _current_entry_id: str | None
    _current_subentry_id: str | None
    _model_list_cache: dict[str, list[anthropic.types.ModelInfo]] | None

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._subentry_iter = None
        self._current_entry_id = None
        self._current_subentry_id = None
        self._model_list_cache = None

    async def async_step_init(
        self, user_input: dict[str, str] | None
    ) -> RepairsFlowResult:
        """Handle the steps of a fix flow."""
        if user_input and user_input.get(CONF_CHAT_MODEL):
            errors = {}
            description_placeholders = (
                self.cur_step["description_placeholders"] if self.cur_step else None
            ) or {}
            try:
                if not await self._async_update_current_subentry(user_input):
                    errors[CONF_CHAT_MODEL] = "model_not_active"
            except anthropic.AnthropicError as err:
                if self.cur_step is None:
                    raise
                errors[CONF_CHAT_MODEL] = "api_error"
                description_placeholders = {
                    **description_placeholders,
                    "message": err.message
                    if isinstance(err, anthropic.APIError)
                    else str(err),
                }
            if errors:
                assert self.cur_step is not None
                return self.async_show_form(
                    step_id=self.cur_step["step_id"],
                    data_schema=self.add_suggested_values_to_schema(
                        cast(probatio.Schema, self.cur_step["data_schema"]), user_input
                    ),
                    errors=errors,
                    description_placeholders=description_placeholders,
                )

        target = await self._async_next_target()
        if target is None:
            return self.async_create_entry(data={})

        entry, subentry, model_info = target
        if self._model_list_cache is None:
            self._model_list_cache = {}
        if entry.entry_id not in self._model_list_cache:
            client = entry.runtime_data.client
            try:
                result = await client.models.list(timeout=10.0)
                models = [model async for model in result]
            except anthropic.AnthropicError:
                models = []
            self._model_list_cache[entry.entry_id] = models
        active_models = [
            model
            for model in self._model_list_cache[entry.entry_id]
            if model.lifecycle == "active"
            and model_alias(model.id) not in DEPRECATED_MODELS
            and model.id not in DEPRECATED_MODELS
        ]
        model_list = [
            SelectOptionDict(
                label=model.display_name,
                value=model_alias(model.id),
            )
            for model in active_models
        ]

        suggested_model = next(
            (
                model_alias(model.id)
                for model in active_models
                if model_info.line is not None and model.line == model_info.line
            ),
            probatio.UNDEFINED,
        )

        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_CHAT_MODEL,
                    default=suggested_model,
                ): SelectSelector(
                    SelectSelectorConfig(options=model_list, custom_value=True)
                ),
            }
        )

        return self.async_show_form(
            step_id="retired" if model_info.lifecycle == "retired" else "init",
            data_schema=schema,
            description_placeholders={
                "entry_name": entry.title,
                "model": model_info.id,
                "subentry_name": subentry.title,
                "subentry_type": self._format_subentry_type(subentry.subentry_type),
                "deprecation_date": model_info.deprecated_at.date().isoformat()
                if model_info.deprecated_at
                else "—",
                "retirement_date": model_info.retires_at.date().isoformat()
                if model_info.retires_at
                else "—",
            },
        )

    async def async_step_retired(
        self, user_input: dict[str, str] | None
    ) -> RepairsFlowResult:
        """Replace a retired model."""
        return await self.async_step_init(user_input)

    def _iter_deprecated_subentries(self) -> Iterator[tuple[str, str]]:
        """Yield entry/subentry pairs that use deprecated models."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            for subentry in entry.subentries.values():
                model = subentry.data.get(CONF_CHAT_MODEL)
                if not model:
                    continue
                model_info, found = entry.runtime_data.get_model_info(model)
                if found and model_info.lifecycle in ("deprecated", "retired"):
                    yield entry.entry_id, subentry.subentry_id

    async def _async_next_target(
        self,
    ) -> tuple[AnthropicConfigEntry, ConfigSubentry, anthropic.types.ModelInfo] | None:
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
            if not model:
                continue
            model_info, found = entry.runtime_data.get_model_info(model)
            if not found or model_info.lifecycle not in ("deprecated", "retired"):
                continue

            self._current_entry_id = entry_id
            self._current_subentry_id = subentry_id
            return entry, subentry, model_info

    async def _async_update_current_subentry(self, user_input: dict[str, str]) -> bool:
        """Update the subentry if the replacement model is active."""
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
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="subentry_not_found"
            )

        updated_data = {
            **subentry.data,
            CONF_CHAT_MODEL: user_input[CONF_CHAT_MODEL],
        }
        alias = model_alias(user_input[CONF_CHAT_MODEL])
        model_info = next(
            (
                model
                for model in (self._model_list_cache or {}).get(entry.entry_id, [])
                if model_alias(model.id) == alias
            ),
            None,
        )
        if model_info is None:
            model_info = await entry.runtime_data.client.models.retrieve(
                user_input[CONF_CHAT_MODEL], timeout=10.0
            )
        if (
            model_info.lifecycle != "active"
            or user_input[CONF_CHAT_MODEL] in DEPRECATED_MODELS
            or model_info.id in DEPRECATED_MODELS
            or model_alias(model_info.id) in DEPRECATED_MODELS
        ):
            return False
        reconcile_model_options(updated_data, model_info)

        self.hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data=updated_data,
        )
        return True

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
    raise HomeAssistantError(
        translation_domain=DOMAIN, translation_key="unknown_issue_id"
    )
