"""Config flow for Nina integration."""

from typing import Any, override

from pynina import ApiError, Nina
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_AREA_FILTER,
    CONF_FILTERS,
    CONF_HEADLINE_FILTER,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    CONST_REGION_MAPPING,
    CONST_REGIONS,
    DEFAULT_AREA_FILTER,
    DEFAULT_HEADLINE_FILTER,
    DOMAIN,
    LOGGER,
    SENSOR_SUFFIXES,
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


def create_regions_schema(regions: dict[str, dict[str, Any]]) -> vol.Schema:
    """Create schema for region selection."""
    schema_dict: VolDictType = {
        **{
            vol.Optional(region): cv.multi_select(regions[region])
            for region in CONST_REGIONS
        },
    }
    return vol.Schema(schema_dict)


def create_options_schema() -> vol.Schema:
    """Create schema for options flow (filters and slots)."""
    schema_dict: VolDictType = {
        vol.Required(
            CONF_MESSAGE_SLOTS,
            default=5,
        ): vol.All(int, vol.Range(min=1, max=20)),
        vol.Required(CONF_FILTERS): section(
            vol.Schema(
                {
                    vol.Optional(
                        CONF_HEADLINE_FILTER,
                    ): cv.string,
                    vol.Optional(
                        CONF_AREA_FILTER,
                    ): cv.string,
                }
            )
        ),
    }
    return vol.Schema(schema_dict)


class NinaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NINA."""

    VERSION: int = 1
    MINOR_VERSION: int = 4

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self._all_region_codes_sorted: dict[str, str] = {}
        self.regions: dict[str, dict[str, Any]] = {}

        for name in CONST_REGIONS:
            self.regions[name] = {}

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}

        if not self._all_region_codes_sorted and (
            region_result := await self._fetch_regions()
        ):
            return region_result

        if user_input is not None and not errors:
            user_input[CONF_REGIONS] = []

            for group in CONST_REGIONS:
                if group_input := user_input.get(group):
                    user_input[CONF_REGIONS] += group_input

            if user_input[CONF_REGIONS]:
                return self.async_create_entry(
                    title="NINA",
                    data=prepare_user_input(user_input, self._all_region_codes_sorted),
                    options={
                        CONF_MESSAGE_SLOTS: 5,
                        CONF_FILTERS: {
                            CONF_HEADLINE_FILTER: DEFAULT_HEADLINE_FILTER,
                            CONF_AREA_FILTER: DEFAULT_AREA_FILTER,
                        },
                    },
                )

            errors["base"] = "no_selection"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                create_regions_schema(self.regions), {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of regions."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors: dict[str, Any] = {}

        if not self._all_region_codes_sorted and (
            region_result := await self._fetch_regions()
        ):
            return region_result

        if user_input is not None and not errors:
            user_input[CONF_REGIONS] = []

            for group in CONST_REGIONS:
                if group_input := user_input.get(group):
                    user_input[CONF_REGIONS] += group_input

            if user_input[CONF_REGIONS]:
                regions_data = prepare_user_input(
                    user_input,
                    self._all_region_codes_sorted,
                )

                await self._remove_unused_devices(reconfigure_entry, regions_data)

                return self.async_update_reload_and_abort(
                    reconfigure_entry, data=user_input
                )

            errors["base"] = "no_selection"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                create_regions_schema(self.regions),
                {**reconfigure_entry.data},
            ),
            errors=errors,
        )

    async def _fetch_regions(self) -> ConfigFlowResult | None:
        """Fetch all regions."""
        nina: Nina = Nina(async_get_clientsession(self.hass))

        try:
            self._all_region_codes_sorted = swap_key_value(
                await nina.get_all_regional_codes()
            )
        except ApiError:
            return self.async_abort(reason="no_fetch")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        self.regions = split_regions(self._all_region_codes_sorted, self.regions)
        return None

    async def _remove_unused_devices(
        self, config_entry: ConfigEntry, regions_data: dict[str, Any]
    ) -> None:
        """Remove devices from regions that are not selected."""
        device_registry = dr.async_get(self.hass)

        removed_regions = set(config_entry.data[CONF_REGIONS]) - set(
            regions_data[CONF_REGIONS]
        )

        for region in removed_regions:
            if device := device_registry.async_get_device_by_identifier(
                (DOMAIN, region), config_entry.entry_id
            ):
                device_registry.async_remove_device(device.id)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle an option flow for NINA - filters and slots only."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow - filters and slots only."""
        if user_input is not None:
            if not user_input[CONF_FILTERS].get(CONF_AREA_FILTER, "").strip():
                user_input[CONF_FILTERS][CONF_AREA_FILTER] = DEFAULT_AREA_FILTER
            if not user_input[CONF_FILTERS].get(CONF_HEADLINE_FILTER, "").strip():
                user_input[CONF_FILTERS][CONF_HEADLINE_FILTER] = DEFAULT_HEADLINE_FILTER

            if CONF_MESSAGE_SLOTS in user_input:
                await self._remove_unused_entities(user_input)

            return self.async_create_entry(title="", data=user_input)

        schema_with_suggested = self.add_suggested_values_to_schema(
            create_options_schema(), dict(self.config_entry.options)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema_with_suggested,
        )

    async def _remove_unused_entities(self, user_input: dict[str, Any]) -> None:
        """Remove entities which are not used anymore due to slot changes."""
        entity_registry = er.async_get(self.hass)

        entries = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        id_type_suffix = [f"-{sensor_id}" for sensor_id in SENSOR_SUFFIXES] + [""]

        old_slots = self.config_entry.options.get(CONF_MESSAGE_SLOTS, 5)
        new_slots = user_input[CONF_MESSAGE_SLOTS]

        if new_slots < old_slots:
            removed_entities_slots = [
                f"{region}-{slot_id}{suffix}"
                for region in self.config_entry.data[CONF_REGIONS]
                for slot_id in range(old_slots + 1)
                for suffix in id_type_suffix
                if slot_id > new_slots
            ]

            removed_uids = set(removed_entities_slots)

            for entry in entries:
                if entry.unique_id in removed_uids:
                    entity_registry.async_remove(entry.entity_id)
