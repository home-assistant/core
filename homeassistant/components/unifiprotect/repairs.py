"""unifiprotect.repairs."""

from __future__ import annotations

from functools import partial
from itertools import chain
import logging
from typing import Any, cast

from pyunifiprotect import ProtectApiClient
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.automation import (
    EVENT_AUTOMATION_RELOADED,
    automations_with_entity,
)
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.components.script import scripts_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_get as async_get_issue_registry,
)

from .const import CONF_ALLOW_EA, DOMAIN
from .utils import async_create_api_client

_LOGGER = logging.getLogger(__name__)


async def async_create_repairs(
    hass: HomeAssistant, entry: ConfigEntry, protect: ProtectApiClient
) -> None:
    """Create any additional repairs for deprecations."""

    await _deprecate_smart_sensor(hass, entry, protect)
    entry.async_on_unload(
        hass.bus.async_listen(
            EVENT_AUTOMATION_RELOADED,
            partial(_deprecate_smart_sensor, hass, entry, protect),
        )
    )


async def _deprecate_smart_sensor(
    hass: HomeAssistant,
    entry: ConfigEntry,
    protect: ProtectApiClient,
    *args: Any,
    **kwargs: Any,
) -> None:
    entity_registry = er.async_get(hass)
    automations: dict[str, list[str]] = {}
    scripts: dict[str, list[str]] = {}
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if (
            entity.domain == Platform.SENSOR
            and entity.disabled_by is None
            and "detected_object" in entity.unique_id
        ):
            entity_automations = automations_with_entity(hass, entity.entity_id)
            entity_scripts = scripts_with_entity(hass, entity.entity_id)
            if entity_automations:
                automations[entity.entity_id] = entity_automations
            if entity_scripts:
                scripts[entity.entity_id] = entity_scripts

    if automations or scripts:
        items = sorted(
            set(
                chain.from_iterable(list(automations.values()) + list(scripts.values()))
            )
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecate_smart_sensor",
            is_fixable=False,
            breaks_in_ha_version="2023.3.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecate_smart_sensor",
            translation_placeholders={"items": "* `" + "`\n* `".join(items) + "`\n"},
        )
    else:
        _LOGGER.debug("No found usages of Detected Object sensor")
        ir.async_delete_issue(hass, DOMAIN, "deprecate_smart_sensor")


class EAConfirm(RepairsFlow):
    """Handler for an issue fixing flow."""

    _api: ProtectApiClient
    _entry: ConfigEntry

    def __init__(self, api: ProtectApiClient, entry: ConfigEntry) -> None:
        """Create flow."""

        self._api = api
        self._entry = entry
        super().__init__()

    @callback
    def _async_get_placeholders(self) -> dict[str, str] | None:
        issue_registry = async_get_issue_registry(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return description_placeholders

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_start()

    async def async_step_start(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is None:
            placeholders = self._async_get_placeholders()
            return self.async_show_form(
                step_id="start",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        nvr = await self._api.get_nvr()
        if await nvr.get_is_prerelease():
            return await self.async_step_confirm()
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        return self.async_create_entry(data={})

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            options = dict(self._entry.options)
            options[CONF_ALLOW_EA] = True
            self.hass.config_entries.async_update_entry(self._entry, options=options)
            return self.async_create_entry(data={})

        placeholders = self._async_get_placeholders()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if data is not None and issue_id == "ea_warning":
        entry_id = cast(str, data["entry_id"])
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
            api = async_create_api_client(hass, entry)
            return EAConfirm(api, entry)
    return ConfirmRepairFlow()
