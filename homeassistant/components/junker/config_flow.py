"""Config flow for Junker."""

import logging
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_AREA_ID,
    CONF_MUNICIPALITY,
    CONF_WASTE_NAME,
    CONF_WASTE_TYPES,
    DOMAIN,
)
from .junker_api import (
    AreaRequired,
    Collection,
    JunkerClient,
    JunkerError,
    slugify_municipality,
)

_LOGGER = logging.getLogger(__name__)
_LOOKUP_URL = "https://junkerapp.it/cerca-il-tuo-comune/"


def _waste_types(collections: list[Collection]) -> list[str]:
    """Return the distinct waste types."""
    return sorted({collection.waste_type for collection in collections})


def _settings_schema(waste_types: list[str], selected: list[str]) -> probatio.Schema:
    """Return the waste types checklist schema."""
    return probatio.Schema(
        {
            probatio.Required(CONF_WASTE_TYPES, default=selected): SelectSelector(
                SelectSelectorConfig(options=waste_types, multiple=True)
            )
        }
    )


def _name_schema(default: str) -> probatio.Schema:
    """Return the schema to rename one waste type."""
    return probatio.Schema({probatio.Required(CONF_WASTE_NAME, default=default): str})


class JunkerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Junker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._municipality = ""
        self._area_id: str | None = None
        self._areas: dict[str, str] = {}
        self._waste_types: list[str] = []
        self._selected: list[str] = []
        self._names: dict[str, str] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the municipality step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            municipality = user_input[CONF_MUNICIPALITY].strip()
            client = JunkerClient(async_get_clientsession(self.hass), municipality)
            try:
                collections = await client.async_get_collections()
            except AreaRequired as err:
                self._municipality = municipality
                self._areas = {str(area.id): area.name for area in err.areas}
                return await self.async_step_area()
            except JunkerError:
                errors["base"] = "invalid_municipality"
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception while validating Junker municipality"
                )
                errors["base"] = "unknown"
            else:
                self._municipality = municipality
                self._waste_types = _waste_types(collections)
                return await self.async_step_settings()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema({probatio.Required(CONF_MUNICIPALITY): str}),
            errors=errors,
            description_placeholders={"lookup_url": _LOOKUP_URL},
        )

    async def async_step_area(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the area selection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            area_id = user_input[CONF_AREA_ID]
            client = JunkerClient(
                async_get_clientsession(self.hass), self._municipality, area_id
            )
            try:
                collections = await client.async_get_collections()
            except JunkerError:
                errors["base"] = "invalid_area"
            except Exception:
                _LOGGER.exception("Unexpected exception while validating Junker area")
                errors["base"] = "unknown"
            else:
                self._area_id = area_id
                self._waste_types = _waste_types(collections)
                return await self.async_step_settings()

        options: list[SelectOptionDict] = [
            {"value": area_id, "label": area_name}
            for area_id, area_name in self._areas.items()
        ]
        return self.async_show_form(
            step_id="area",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_AREA_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the waste types step."""
        await self.async_set_unique_id(
            f"{slugify_municipality(self._municipality)}:{self._area_id or 'all'}"
        )
        self._abort_if_unique_id_configured()
        if user_input is not None:
            self._selected = user_input[CONF_WASTE_TYPES]
            self._names = {}
            return await self.async_step_names()
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(self._waste_types, self._waste_types),
        )

    async def async_step_names(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Rename each selected waste type, one at a time."""
        if user_input is not None:
            self._names[self._selected[len(self._names)]] = user_input[CONF_WASTE_NAME]
        if len(self._names) == len(self._selected):
            data = {CONF_MUNICIPALITY: self._municipality}
            title = self._municipality
            if self._area_id is not None:
                data[CONF_AREA_ID] = self._area_id
                title = f"{self._municipality} ({self._areas[self._area_id]})"
            return self.async_create_entry(
                title=title, data=data, options={CONF_WASTE_TYPES: self._names}
            )
        waste_type = self._selected[len(self._names)]
        return self.async_show_form(
            step_id="names",
            data_schema=_name_schema(waste_type),
            description_placeholders={"waste_type": waste_type},
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> JunkerOptionsFlow:
        """Return the options flow."""
        return JunkerOptionsFlow()


class JunkerOptionsFlow(OptionsFlowWithReload):
    """Handle Junker options."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._selected: list[str] = []
        self._names: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the waste types."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        if user_input is not None:
            self._selected = user_input[CONF_WASTE_TYPES]
            self._names = {}
            return await self.async_step_names()

        current = self.config_entry.options.get(CONF_WASTE_TYPES, {})
        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(
                _waste_types(self.config_entry.runtime_data.data), list(current)
            ),
        )

    async def async_step_names(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Rename each selected waste type, one at a time."""
        if user_input is not None:
            self._names[self._selected[len(self._names)]] = user_input[CONF_WASTE_NAME]
        if len(self._names) == len(self._selected):
            return self.async_create_entry(data={CONF_WASTE_TYPES: self._names})
        waste_type = self._selected[len(self._names)]
        current = self.config_entry.options.get(CONF_WASTE_TYPES, {})
        return self.async_show_form(
            step_id="names",
            data_schema=_name_schema(current.get(waste_type, waste_type)),
            description_placeholders={"waste_type": waste_type},
        )
