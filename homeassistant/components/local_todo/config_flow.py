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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.util import slugify

from . import LocalTodoConfigEntry, get_store
from .const import (
    CONF_CATEGORIES,
    CONF_CATEGORY,
    CONF_NEW_NAME,
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

CATEGORIES_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_CATEGORIES, default=[]): TextSelector(
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
    def _categories(self) -> list[str]:
        return list(self.config_entry.options.get(CONF_CATEGORIES, []))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to manage the categories."""
        if not await self._async_known_categories():
            return await self.async_step_categories()
        return self.async_show_menu(
            step_id="init", menu_options=["categories", "rename_category"]
        )

    async def async_step_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add and remove the categories of the To-do list."""
        errors: dict[str, str] = {}
        known = await self._async_known_categories()
        if user_input is not None:
            stripped = (category.strip() for category in user_input[CONF_CATEGORIES])
            categories = list(dict.fromkeys(filter(None, stripped)))
            if any("," in category for category in categories):
                errors[CONF_CATEGORIES] = "invalid_category"
            else:
                removed = set(known) - set(categories)
                try:
                    await self._async_change_categories(
                        categories, dict.fromkeys(removed)
                    )
                except HomeAssistantError:
                    errors["base"] = "cannot_save"
                else:
                    return self.async_create_entry(data={CONF_CATEGORIES: categories})

        return self.async_show_form(
            step_id="categories",
            data_schema=self.add_suggested_values_to_schema(
                CATEGORIES_SCHEMA, user_input or {CONF_CATEGORIES: known}
            ),
            errors=errors,
        )

    async def async_step_rename_category(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Rename a category, keeping its items in it."""
        known = await self._async_known_categories()
        errors: dict[str, str] = {}
        if user_input is not None:
            category = user_input[CONF_CATEGORY]
            new_name = user_input[CONF_NEW_NAME].strip()
            if not new_name or "," in new_name:
                errors[CONF_NEW_NAME] = "invalid_category"
            elif new_name != category and new_name in known:
                errors[CONF_NEW_NAME] = "category_exists"
            else:
                categories = [
                    new_name if declared == category else declared
                    for declared in self._categories
                ]
                try:
                    await self._async_change_categories(
                        categories, {category: new_name}
                    )
                except HomeAssistantError:
                    errors["base"] = "cannot_save"
                else:
                    return self.async_create_entry(data={CONF_CATEGORIES: categories})

        schema = probatio.Schema(
            {
                probatio.Required(CONF_CATEGORY): SelectSelector(
                    SelectSelectorConfig(options=known)
                ),
                probatio.Required(CONF_NEW_NAME): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="rename_category",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def _async_known_categories(self) -> list[str]:
        """Return the declared categories, then the other ones used by items."""
        if self.config_entry.state is ConfigEntryState.LOADED and (
            entity := self.config_entry.runtime_data.entity
        ):
            used = [item.category for item in entity.todo_items or () if item.category]
        else:
            used = await get_store(
                self.hass, self.config_entry
            ).async_get_item_categories()
        return list(dict.fromkeys([*self._categories, *used]))

    async def _async_change_categories(
        self, categories: list[str], changes: Mapping[str, str | None]
    ) -> None:
        """Apply category changes to the list before saving the options."""
        # Hold the setup lock so the entry can't load a stale copy of the file
        async with self.config_entry.setup_lock:
            if self.config_entry.state is ConfigEntryState.LOADED:
                data = self.config_entry.runtime_data
                if data.entity is not None:
                    await data.entity.async_change_categories(categories, changes)
                    return
                # The entity is disabled: enabling it reloads the entry from disk
                store = data.store
            else:
                store = get_store(self.hass, self.config_entry)
            if changes:
                await store.async_change_categories(changes)
