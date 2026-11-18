"""LLM tools for the energy integration."""

from typing import cast, override

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
from homeassistant.util.json import JsonValueType, json_loads

from .const import DOMAIN
from .data import (
    DEVICE_CONSUMPTION_SCHEMA,
    ENERGY_SOURCE_SCHEMA,
    EnergyManager,
    EnergyPreferencesUpdate,
    async_get_manager,
)
from .validate import async_validate

_DEVICE_CONSUMPTION_DESCRIPTION = (
    "devices, each with stat_consumption (an energy statistic ID), and optionally "
    "name, stat_rate (a power statistic ID) and included_in_stat (the "
    "stat_consumption of a device that already measures this device)."
)

# The tool parameters are plain lists, because the full schemas are too large
# and complex to send to the LLM with every request. They are validated in
# async_call instead.
_UPDATE_SCHEMA = probatio.Schema(
    {
        probatio.Optional("energy_sources"): ENERGY_SOURCE_SCHEMA,
        probatio.Optional("device_consumption"): [DEVICE_CONSUMPTION_SCHEMA],
        probatio.Optional("device_consumption_water"): [DEVICE_CONSUMPTION_SCHEMA],
        probatio.Optional("device_consumption_gas"): [DEVICE_CONSUMPTION_SCHEMA],
    }
)


class GetPreferencesTool(Tool):
    """LLM Tool to get the energy preferences."""

    name = "energy__get_preferences"
    title = "Get energy preferences"
    description = (
        "Get the energy preferences that the energy dashboard uses: the energy "
        "sources (grid, solar, battery, gas, water and home) and the devices that "
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
        return ToolResult(
            data={
                "result": cast(
                    JsonValueType, manager.data or EnergyManager.default_preferences()
                )
            }
        )


class UpdatePreferencesTool(Tool):
    """LLM Tool to update the energy preferences."""

    name = "energy__update_preferences"
    title = "Update energy preferences"
    description = (
        "Update the energy preferences that the energy dashboard uses. Each given "
        "list replaces the complete current list, so get the preferences first and "
        "send all items of a list, also the items that do not change. Lists that "
        "are not given stay the same. Returns the new preferences and the "
        "validation issues of each item."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "energy_sources",
                description=(
                    "The energy sources. Each has a type: grid, solar, battery, "
                    "gas, water or home, and the statistic IDs of its meters, "
                    "for example stat_energy_from and stat_energy_to."
                ),
            ): [dict],
            probatio.Optional(
                "device_consumption",
                description=f"The electricity {_DEVICE_CONSUMPTION_DESCRIPTION}",
            ): [dict],
            probatio.Optional(
                "device_consumption_water",
                description=f"The water {_DEVICE_CONSUMPTION_DESCRIPTION}",
            ): [dict],
            probatio.Optional(
                "device_consumption_gas",
                description=f"The gas {_DEVICE_CONSUMPTION_DESCRIPTION}",
            ): [dict],
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Update the energy preferences."""
        try:
            update = _UPDATE_SCHEMA(self.parameters(tool_input.tool_args))
        except probatio.Invalid as err:
            return ToolResult(data={"error": str(err)}, error=True)
        manager = await async_get_manager(hass)
        await manager.async_update(cast(EnergyPreferencesUpdate, update))
        validation = await async_validate(hass)
        return ToolResult(
            data={
                "result": cast(JsonValueType, manager.data),
                # The issues hold sets of tuples, which plain JSON encoders reject
                "validation": json_loads(json_dumps(validation.as_dict())),
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
