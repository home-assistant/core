"""Config flow for Local To-do integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.util import slugify

from . import LocalTodoConfigEntry, get_store
from .const import (
    CONF_NEW_NAME,
    CONF_SECTION,
    CONF_SECTIONS,
    CONF_STORAGE_KEY,
    CONF_TODO_LIST_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TODO_LIST_NAME): str,
    }
)

SECTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_SECTIONS, default=[]): TextSelector(
            TextSelectorConfig(multiple=True)
        ),
    }
)


class LocalTodoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local To-do."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> LocalTodoOptionsFlow:
        """Get the options flow for this handler."""
        return LocalTodoOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            key = slugify(user_input[CONF_TODO_LIST_NAME])
            self._async_abort_entries_match({CONF_STORAGE_KEY: key})
            user_input[CONF_STORAGE_KEY] = key
            return self.async_create_entry(
                title=user_input[CONF_TODO_LIST_NAME], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class LocalTodoOptionsFlow(OptionsFlow):
    """Handle the options of a Local To-do list."""

    config_entry: LocalTodoConfigEntry

    @property
    def _sections(self) -> list[str]:
        return list(self.config_entry.options.get(CONF_SECTIONS, []))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to manage the sections."""
        if not self._sections:
            return await self.async_step_sections()
        return self.async_show_menu(
            step_id="init", menu_options=["sections", "rename_section"]
        )

    async def async_step_sections(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add, remove and order the sections of the To-do list."""
        errors: dict[str, str] = {}
        if user_input is not None:
            stripped = (section.strip() for section in user_input[CONF_SECTIONS])
            sections = list(dict.fromkeys(filter(None, stripped)))
            if any("," in section for section in sections):
                errors[CONF_SECTIONS] = "invalid_section"
            else:
                removed = set(self._sections) - set(sections)
                await self._async_change_sections(sections, dict.fromkeys(removed))
                return self.async_create_entry(data={CONF_SECTIONS: sections})

        return self.async_show_form(
            step_id="sections",
            data_schema=self.add_suggested_values_to_schema(
                SECTIONS_SCHEMA, user_input or self.config_entry.options
            ),
            errors=errors,
        )

    async def async_step_rename_section(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Rename a section, keeping its items in it."""
        sections = self._sections
        errors: dict[str, str] = {}
        if user_input is not None:
            section = user_input[CONF_SECTION]
            new_name = user_input[CONF_NEW_NAME].strip()
            if not new_name or "," in new_name:
                errors[CONF_NEW_NAME] = "invalid_section"
            elif new_name != section and new_name in sections:
                errors[CONF_NEW_NAME] = "section_exists"
            else:
                sections[sections.index(section)] = new_name
                await self._async_change_sections(sections, {section: new_name})
                return self.async_create_entry(data={CONF_SECTIONS: sections})

        schema = probatio.Schema(
            {
                probatio.Required(CONF_SECTION): SelectSelector(
                    SelectSelectorConfig(options=sections)
                ),
                probatio.Required(CONF_NEW_NAME): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="rename_section",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def _async_change_sections(
        self, sections: list[str], changes: Mapping[str, str | None]
    ) -> None:
        """Apply section changes to the list before saving the options."""
        if self.config_entry.state is ConfigEntryState.LOADED:
            data = self.config_entry.runtime_data
            if data.entity is not None:
                await data.entity.async_change_sections(sections, changes)
                return
            # The entity is disabled: enabling it reloads the entry from disk
            store = data.store
        else:
            store = get_store(self.hass, self.config_entry)
        if changes:
            await store.async_change_sections(changes)
