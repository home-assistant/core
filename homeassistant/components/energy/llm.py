"""LLM tools for the energy integration."""

from typing import TYPE_CHECKING, Any, cast, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.json import JsonObjectType, json_loads_object

from .const import BATTERY_DIRECTIONS, DOMAIN
from .data import (
    DEVICE_CONSUMPTION_SCHEMA,
    ENERGY_SOURCE_SCHEMA,
    EnergyManager,
    EnergyPreferences,
    EnergyPreferencesUpdate,
    async_get_manager,
)
from .validate import async_validate

_SOURCE_KEYS = {
    "grid": "grid_sources",
    "solar": "solar_sources",
    "battery": "battery_sources",
    "gas": "gas_sources",
    "water": "water_sources",
    "home": "home_sources",
}
_DEVICE_KEYS = (
    "device_consumption",
    "device_consumption_water",
    "device_consumption_gas",
)

# The tool parameters only declare the fields, so every LLM can fill them in.
# The schemas of data.py validate the values in async_call.
_STR_OR_NONE = probatio.Any(None, str)
_FLOAT_OR_NONE = probatio.Any(None, probatio.Coerce(float))

_POWER_CONFIG: VolDictType = {
    probatio.Optional("stat_rate"): str,
    probatio.Optional("stat_rate_inverted"): str,
    probatio.Optional("stat_rate_from"): str,
    probatio.Optional("stat_rate_to"): str,
}
_POWER_CONFIG_DESCRIPTION = (
    "Power sensors, used instead of stat_rate: one sensor in stat_rate, one with "
    "the opposite sign in stat_rate_inverted, or one per direction in "
    "stat_rate_from and stat_rate_to."
)
_COSTS: VolDictType = {
    probatio.Optional("stat_cost"): _STR_OR_NONE,
    probatio.Optional("entity_energy_price"): _STR_OR_NONE,
    probatio.Optional("number_energy_price"): _FLOAT_OR_NONE,
}
_COSTS_DESCRIPTION = (
    "The costs come from the statistic in stat_cost, or from a price per unit in "
    "the entity in entity_energy_price or the number in number_energy_price."
)

_GRID_SOURCE: VolDictType = {
    probatio.Optional("stat_energy_from"): _STR_OR_NONE,
    probatio.Optional("stat_energy_to"): _STR_OR_NONE,
    **_COSTS,
    probatio.Optional("stat_compensation"): _STR_OR_NONE,
    probatio.Optional("entity_energy_price_export"): _STR_OR_NONE,
    probatio.Optional("number_energy_price_export"): _FLOAT_OR_NONE,
    probatio.Optional("stat_rate"): str,
    probatio.Optional("power_config", description=_POWER_CONFIG_DESCRIPTION): (
        _POWER_CONFIG
    ),
    probatio.Optional("name"): str,
}
_SOLAR_SOURCE: VolDictType = {
    probatio.Required("stat_energy_from"): str,
    probatio.Optional("stat_rate"): str,
    probatio.Optional("config_entry_solar_forecast"): probatio.Any(None, [str]),
    probatio.Optional("name"): str,
}
_BATTERY_SOURCE: VolDictType = {
    probatio.Optional("stat_energy_from"): str,
    probatio.Optional("stat_energy_to"): str,
    **{probatio.Optional(energy_key): str for energy_key, _ in BATTERY_DIRECTIONS},
    probatio.Optional("stat_rate"): str,
    probatio.Optional("power_config", description=_POWER_CONFIG_DESCRIPTION): {
        **_POWER_CONFIG,
        **{probatio.Optional(power_key): str for _, power_key in BATTERY_DIRECTIONS},
    },
    probatio.Optional("stat_soc"): str,
    probatio.Optional("capacity"): probatio.Coerce(float),
    probatio.Optional("entity_capacity"): str,
    probatio.Optional("name"): str,
}
_METER_SOURCE: VolDictType = {
    probatio.Required("stat_energy_from"): str,
    probatio.Optional("stat_rate"): str,
    **_COSTS,
    probatio.Optional("name"): str,
}
_HOME_SOURCE: VolDictType = {
    probatio.Required("stat_energy_to"): str,
    probatio.Optional("stat_rate"): str,
    probatio.Optional("name"): str,
}
_DEVICE_DESCRIPTION = (
    "devices. stat_consumption is the meter of the device, included_in_stat the "
    "stat_consumption of a device whose meter also measures this device."
)

_PARAMETERS = probatio.Schema(
    {
        probatio.Optional(
            "grid_sources",
            description=(
                "Grid connections. stat_energy_from is the meter of the energy from "
                "the grid, stat_energy_to of the energy returned to the grid. "
                f"{_COSTS_DESCRIPTION} stat_compensation, "
                "entity_energy_price_export and number_energy_price_export do the "
                "same for the returned energy."
            ),
        ): [_GRID_SOURCE],
        probatio.Optional(
            "solar_sources",
            description=(
                "Solar panels. stat_energy_from is the meter of the produced energy. "
                "config_entry_solar_forecast lists the config entry IDs of solar "
                "forecast integrations."
            ),
        ): [_SOLAR_SOURCE],
        probatio.Optional(
            "battery_sources",
            description=(
                "Home batteries, measured in total with stat_energy_from "
                "(discharged) and stat_energy_to (charged), or per direction with "
                "stat_energy_from_grid, stat_energy_from_solar, stat_energy_to_home "
                "and stat_energy_to_grid. stat_soc is the state of charge in %, "
                "capacity the usable capacity in kWh, or entity_capacity a sensor "
                "with the usable capacity."
            ),
        ): [_BATTERY_SOURCE],
        probatio.Optional(
            "gas_sources",
            description=(
                "Gas meters. stat_energy_from is the meter of the used gas. "
                f"{_COSTS_DESCRIPTION}"
            ),
        ): [_METER_SOURCE],
        probatio.Optional(
            "water_sources",
            description=(
                "Water meters. stat_energy_from is the meter of the used water. "
                f"{_COSTS_DESCRIPTION}"
            ),
        ): [_METER_SOURCE],
        probatio.Optional(
            "home_sources",
            description=(
                "At most one meter of all the energy the home uses, in stat_energy_to."
            ),
        ): [_HOME_SOURCE],
        probatio.Optional(
            "device_consumption", description=f"Electricity {_DEVICE_DESCRIPTION}"
        ): [DEVICE_CONSUMPTION_SCHEMA],
        probatio.Optional(
            "device_consumption_water", description=f"Water {_DEVICE_DESCRIPTION}"
        ): [DEVICE_CONSUMPTION_SCHEMA],
        probatio.Optional(
            "device_consumption_gas", description=f"Gas {_DEVICE_DESCRIPTION}"
        ): [DEVICE_CONSUMPTION_SCHEMA],
    }
)


def _split_by_type(
    preferences: EnergyPreferences, values: list[Any]
) -> dict[str, list[Any]]:
    """Return the values of the energy sources, in the same order, per source type."""
    split: dict[str, list[Any]] = {key: [] for key in _SOURCE_KEYS.values()}
    for source, value in zip(preferences["energy_sources"], values, strict=True):
        split[_SOURCE_KEYS[source["type"]]].append(value)
    return split


def _format_preferences(preferences: EnergyPreferences) -> JsonObjectType:
    """Return the preferences with the energy sources per type, without the type."""
    sources = [
        {key: value for key, value in source.items() if key != "type"}
        for source in preferences["energy_sources"]
    ]
    return cast(
        JsonObjectType,
        {
            **_split_by_type(preferences, sources),
            **{key: preferences.get(key, []) for key in _DEVICE_KEYS},
        },
    )


class GetPreferencesTool(Tool):
    """LLM Tool to get the energy preferences."""

    name = "energy__get_preferences"
    title = "Get energy preferences"
    description = (
        "Get the energy preferences that the energy dashboard uses: the grid, "
        "solar, battery, gas, water and home energy sources, and the devices that "
        "track their electricity, water and gas consumption."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the energy preferences."""
        manager = await async_get_manager(hass)
        preferences = manager.data or EnergyManager.default_preferences()
        return ToolResult(data=_format_preferences(preferences))


class UpdatePreferencesTool(Tool):
    """LLM Tool to update the energy preferences."""

    name = "energy__update_preferences"
    title = "Update energy preferences"
    description = (
        "Update the energy preferences that the energy dashboard uses. Each given "
        "list replaces the complete current list, so get the preferences first and "
        "send all items of a list, also the items that do not change. Lists that "
        "are not given stay the same. Fields that start with stat_ hold statistic "
        "IDs, usually the entity IDs of sensors. stat_rate is a power or flow rate "
        "sensor. Returns the new preferences and the validation issues of each item."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = _PARAMETERS

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Update the energy preferences."""
        args = self.parameters(tool_input.tool_args)
        manager = await async_get_manager(hass)
        current = manager.data or EnergyManager.default_preferences()

        update: dict[str, Any] = {key: args[key] for key in _DEVICE_KEYS if key in args}
        if any(key in args for key in _SOURCE_KEYS.values()):
            lists = {**_format_preferences(current), **args}
            sources = [
                {"type": source_type, **item}
                for source_type, key in _SOURCE_KEYS.items()
                for item in lists[key]
            ]
            try:
                update["energy_sources"] = ENERGY_SOURCE_SCHEMA(sources)
            except probatio.Invalid as err:
                return ToolResult(data={"error": str(err)}, error=True)

        await manager.async_update(cast(EnergyPreferencesUpdate, update))
        # The issues hold sets of tuples, which plain JSON encoders reject
        validation = json_loads_object(
            json_dumps((await async_validate(hass)).as_dict())
        )
        preferences = manager.data
        if TYPE_CHECKING:
            assert preferences is not None
        energy_validation = cast(list[Any], validation.pop("energy_sources"))
        return ToolResult(
            data={
                "preferences": _format_preferences(preferences),
                "validation": {
                    **_split_by_type(preferences, energy_validation),
                    **validation,
                },
            }
        )


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the energy LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None
    return LLMTools(tools=[GetPreferencesTool(), UpdatePreferencesTool()])
