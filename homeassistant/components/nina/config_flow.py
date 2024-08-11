"""Config flow for Nina integration."""

from __future__ import annotations

from typing import Any

from pynina import ApiError, Nina
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import (
    _LOGGER,
    CONF_AREA_FILTER,
    CONF_HEADLINE_FILTER,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    CONST_REGION_MAPPING,
    CONST_REGIONS,
    DOMAIN,
    NO_MATCH_REGEX,
)


def swap_key_value(dict_to_sort: dict[str, str]) -> dict[str, str]:
    """Swap keys and values in dict."""
    all_region_codes_swaped: dict[str, str] = {}

    for key, value in dict_to_sort.items():
        if value not in all_region_codes_swaped:
            all_region_codes_swaped[value] = key
        else:
            for i in range(len(dict_to_sort)):
                tmp_value: str = f"{value}_{i}"
                if tmp_value not in all_region_codes_swaped:
                    all_region_codes_swaped[tmp_value] = key
                    break

    return dict(sorted(all_region_codes_swaped.items(), key=lambda ele: ele[1]))


def split_regions(
    _all_region_codes_sorted: dict[str, str], regions: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Split regions alphabetical."""
    for index, name in _all_region_codes_sorted.items():
        for region_name, grouping_letters in CONST_REGION_MAPPING.items():
            if name[0] in grouping_letters:
                regions[region_name][index] = name
                break
    return regions


def prepare_user_input(
    user_input: dict[str, Any], _all_region_codes_sorted: dict[str, str]
) -> dict[str, Any]:
    """Prepare the user inputs."""
    tmp: dict[str, Any] = {}

    for reg in user_input[CONF_REGIONS]:
        tmp[_all_region_codes_sorted[reg]] = reg.split("_", 1)[0]

    compact: dict[str, Any] = {}

    for key, val in tmp.items():
        if val in compact:
            # Abenberg, St + Abenberger Wald
            compact[val] = f"{compact[val]} + {key}"
            break
        compact[val] = key

    user_input[CONF_REGIONS] = compact

    return user_input


class NinaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NINA."""

    VERSION: int = 1

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self._all_region_codes_sorted: dict[str, str] = {}
        self.regions: dict[str, dict[str, Any]] = {}

        for name in CONST_REGIONS:
            self.regions[name] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}

        if not self._all_region_codes_sorted:
            nina: Nina = Nina(async_get_clientsession(self.hass))

            try:
                self._all_region_codes_sorted = swap_key_value(
                    await nina.getAllRegionalCodes()
                )
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception: %s", err)
                return self.async_abort(reason="unknown")

            self.regions = split_regions(self._all_region_codes_sorted, self.regions)

        if user_input is not None and not errors:
            user_input[CONF_REGIONS] = []

            for group in CONST_REGIONS:
                if group_input := user_input.get(group):
                    user_input[CONF_REGIONS] += group_input

            if not user_input[CONF_HEADLINE_FILTER]:
                user_input[CONF_HEADLINE_FILTER] = NO_MATCH_REGEX

            if user_input[CONF_REGIONS]:
                return self.async_create_entry(
                    title="NINA",
                    data=prepare_user_input(user_input, self._all_region_codes_sorted),
                )

            errors["base"] = "no_selection"

        regions_schema: VolDictType = {
            vol.Optional(region): cv.multi_select(self.regions[region])
            for region in CONST_REGIONS
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    **regions_schema,
                    vol.Required(CONF_MESSAGE_SLOTS, default=5): vol.All(
                        int, vol.Range(min=1, max=20)
                    ),
                    vol.Optional(CONF_HEADLINE_FILTER, default=""): cv.string,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for nut."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.data = dict(self.config_entry.data)

        self._all_region_codes_sorted: dict[str, str] = {}
        self.regions: dict[str, dict[str, Any]] = {}

        for name in CONST_REGIONS:
            self.regions[name] = {}
            if name not in self.data:
                self.data[name] = []

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        errors: dict[str, Any] = {}

        if not self._all_region_codes_sorted:
            nina: Nina = Nina(async_get_clientsession(self.hass))

            try:
                self._all_region_codes_sorted = swap_key_value(
                    await nina.getAllRegionalCodes()
                )
            except ApiError:
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception: %s", err)
                return self.async_abort(reason="unknown")

            self.regions = split_regions(self._all_region_codes_sorted, self.regions)

        if user_input is not None and not errors:
            user_input[CONF_REGIONS] = []

            for group in CONST_REGIONS:
                if group_input := user_input.get(group):
                    user_input[CONF_REGIONS] += group_input

            if user_input[CONF_REGIONS]:
                user_input = prepare_user_input(
                    user_input, self._all_region_codes_sorted
                )

                entity_registry = er.async_get(self.hass)

                entries = er.async_entries_for_config_entry(
                    entity_registry, self.config_entry.entry_id
                )

                removed_entities_slots = [
                    f"{region}-{slot_id}"
                    for region in self.data[CONF_REGIONS]
                    for slot_id in range(self.data[CONF_MESSAGE_SLOTS] + 1)
                    if slot_id > user_input[CONF_MESSAGE_SLOTS]
                ]

                removed_entites_area = [
                    f"{cfg_region}-{slot_id}"
                    for slot_id in range(1, self.data[CONF_MESSAGE_SLOTS] + 1)
                    for cfg_region in self.data[CONF_REGIONS]
                    if cfg_region not in user_input[CONF_REGIONS]
                ]

                for entry in entries:
                    for entity_uid in list(
                        set(removed_entities_slots + removed_entites_area)
                    ):
                        if entry.unique_id == entity_uid:
                            entity_registry.async_remove(entry.entity_id)

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input
                )

                return self.async_create_entry(title="", data=None)

            errors["base"] = "no_selection"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    **{
                        vol.Optional(
                            region, default=self.data[region]
                        ): cv.multi_select(self.regions[region])
                        for region in CONST_REGIONS
                    },
                    vol.Required(
                        CONF_MESSAGE_SLOTS,
                        default=self.data[CONF_MESSAGE_SLOTS],
                    ): vol.All(int, vol.Range(min=1, max=20)),
                    vol.Optional(
                        CONF_HEADLINE_FILTER,
                        default=self.data[CONF_HEADLINE_FILTER],
                    ): cv.string,
                    vol.Optional(
                        CONF_AREA_FILTER,
                        default=self.data[CONF_AREA_FILTER],
                    ): cv.string,
                }
            ),
            errors=errors,
        )
