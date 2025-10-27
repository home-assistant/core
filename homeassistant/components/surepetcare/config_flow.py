"""Config flow for Sure Petcare integration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from types import MappingProxyType
from typing import Any, cast

import surepy
from surepy.entities.devices import Flap
from surepy.enums import EntityType
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_CREATE_PET_SELECT,
    CONF_FLAPS_MAPPINGS,
    CONF_MANUALLY_SET_LOCATION,
    CONF_PET_SELECT_OPTIONS,
    DOMAIN,
    SURE_API_TIMEOUT,
)
from .types import FlapMappings

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SurePetCareConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sure Petcare."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            client = surepy.Surepy(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                auth_token=None,
                api_timeout=SURE_API_TIMEOUT,
                session=async_get_clientsession(self.hass),
            )
            try:
                token = await client.sac.get_token()
            except SurePetcareAuthenticationError:
                errors["base"] = "invalid_auth"
            except SurePetcareError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Sure Petcare",
                    data={**user_input, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            client = surepy.Surepy(
                reauth_entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                auth_token=None,
                api_timeout=SURE_API_TIMEOUT,
                session=async_get_clientsession(self.hass),
            )
            try:
                token = await client.sac.get_token()
            except SurePetcareAuthenticationError:
                errors["base"] = "invalid_auth"
            except SurePetcareError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"username": reauth_entry.data[CONF_USERNAME]},
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CREATE_PET_SELECT): bool,
    }
)


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle a option flow for Sure Petcare."""

    _flaps: list[Flap] = []
    _areas: Iterable[ar.AreaEntry] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""

        if user_input is not None:
            if user_input[CONF_CREATE_PET_SELECT]:
                return await self.async_step_pet_select_config()
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )

    async def async_step_pet_select_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the configuration for the pet location select entities."""
        errors = {}

        if user_input is not None:
            errors = self._validate_pet_select_config_user_input(user_input)

            if not errors:
                config_entry_data = self._build_pet_select_config_entry(user_input)
                return self.async_create_entry(
                    data=config_entry_data,
                )
        else:
            self._flaps = []
            client = surepy.Surepy(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
                auth_token=self.config_entry.data[CONF_TOKEN],
                api_timeout=SURE_API_TIMEOUT,
                session=async_get_clientsession(self.hass),
            )
            try:
                devices = await client.get_devices()
            except SurePetcareAuthenticationError:
                errors["base"] = "invalid_auth"
            except SurePetcareError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._flaps = [
                    cast(Flap, device)
                    for device in devices
                    if device.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP]
                ]

            area_reg = ar.async_get(self.hass)
            self._areas = area_reg.async_list_areas()

        data_schema, description_placeholders = self._get_pet_select_config_schema(
            user_input
            or self._extract_default_input_from_options(self.config_entry.options)
        )

        return self.async_show_form(
            step_id="pet_select_config",
            data_schema=data_schema,
            description_placeholders=description_placeholders,
            errors=errors,
        )

    def _extract_default_input_from_options(
        self, options: MappingProxyType[str, Any]
    ) -> dict[str, Any]:
        """Extract pet select related input from user input."""
        default_input: dict[str, Any] = {}
        default_input[CONF_CREATE_PET_SELECT] = options.get(
            CONF_CREATE_PET_SELECT, False
        )
        default_input[CONF_MANUALLY_SET_LOCATION] = options.get(
            CONF_MANUALLY_SET_LOCATION, {}
        )
        default_input.update(options.get(CONF_FLAPS_MAPPINGS, {}))
        return default_input

    def _build_pet_select_config_entry(
        self, user_input: dict[str, Any]
    ) -> Mapping[str, Any]:
        """Build the pet location select entity config entry."""
        config_entry_data: dict[str, Any] = {}

        config_entry_data[CONF_CREATE_PET_SELECT] = True
        config_entry_data[CONF_MANUALLY_SET_LOCATION] = user_input[
            CONF_MANUALLY_SET_LOCATION
        ]

        flaps_mappings: dict[str, FlapMappings] = {}
        selected_zones = set()
        selected_zones.add(user_input[CONF_MANUALLY_SET_LOCATION]["entry"])
        selected_zones.add(user_input[CONF_MANUALLY_SET_LOCATION]["exit"])

        for idx, flap in enumerate(self._flaps):
            flap_id = str(flap.id)
            value = user_input[self._get_flap_static_key(idx)]
            flaps_mappings[flap_id] = {
                "entry": value["entry"],
                "exit": value["exit"],
            }
            selected_zones.add(value["exit"])
            selected_zones.add(value["entry"])

        config_entry_data[CONF_FLAPS_MAPPINGS] = flaps_mappings
        config_entry_data[CONF_PET_SELECT_OPTIONS] = sorted(selected_zones)

        return config_entry_data

    def _get_pet_select_config_schema(
        self, default_input: dict[str, Any] | None
    ) -> tuple[vol.Schema, dict[str, str]]:
        """Return the schema for the pet location select entity config form.

        Retain info already provided for future form views by setting them
        as defaults in schema.
        """
        if default_input is None:
            default_input = {}

        areas_options = [area.name for area in self._areas]
        options = [*areas_options, ""]
        zones_selector = SelectSelector(
            SelectSelectorConfig(
                options=options,
                mode=SelectSelectorMode.DROPDOWN,
                multiple=False,
                custom_value=True,
            )
        )

        data_schema: VolDictType = {}
        description_placeholders: dict[str, str] = {}
        for idx, flap in enumerate(self._flaps):
            flap_id = str(flap.id)
            description_placeholders[f"flap_name_{idx + 1}"] = flap.name
            flap_default_input = default_input.get(flap_id, {})
            data_schema[vol.Required(self._get_flap_static_key(idx))] = section(
                self._get_pet_select_config_section_schema(
                    zones_selector,
                    default_entry=flap_default_input.get("entry", ""),
                    default_exit=flap_default_input.get("exit", ""),
                ),
                {"collapsed": False},
            )

        manual_default_input = default_input.get(CONF_MANUALLY_SET_LOCATION, {})
        data_schema[vol.Required(CONF_MANUALLY_SET_LOCATION)] = section(
            self._get_pet_select_config_section_schema(
                zones_selector,
                default_entry=manual_default_input.get("entry", ""),
                default_exit=manual_default_input.get("exit", ""),
            ),
            {"collapsed": False},
        )

        return vol.Schema(data_schema), description_placeholders

    def _get_flap_static_key(
        self,
        idx: int,
    ) -> str:
        """Return the static key for the flap at index idx."""
        return f"flap_{idx + 1}"

    def _get_pet_select_config_section_schema(
        self,
        zones_selector: SelectSelector,
        default_entry: str = "",
        default_exit: str = "",
    ) -> vol.Schema:
        """Return the schema for the flaps and manually set location sections of the pet location select entity config form."""
        return vol.Schema(
            {
                vol.Required("exit", default=default_exit): zones_selector,
                vol.Required("entry", default=default_entry): zones_selector,
            }
        )

    def _validate_pet_select_config_user_input(
        self,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate user input for pet location select entity config step."""
        errors = {}

        manually_set_location = user_input[CONF_MANUALLY_SET_LOCATION]
        if (
            manually_set_location.get("entry").strip() == ""
            or manually_set_location.get("exit").strip() == ""
        ):
            errors["base"] = "no_zones_selected"
            return errors

        for idx, _ in enumerate(self._flaps):
            flap_static_key = self._get_flap_static_key(idx)
            value = user_input[flap_static_key]
            if value["entry"].strip() == "" or value["exit"].strip() == "":
                errors[flap_static_key] = "no_zones_selected"
                return errors

        return errors
