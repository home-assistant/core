"""LLM tools for generating Lovelace dashboards."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    llm,
)
from homeassistant.util.json import JsonObjectType

API_ID = "lovelace_dashboard_generation"
API_NAME = "Lovelace Dashboard Generation"
API_PROMPT = """Use the list tools to discover available areas, devices and entities.
Always reference real entity_ids from tool results when building dashboard cards.
Return dashboard data that includes a top-level `views` array."""

GENERATE_GUIDELINES = Path(__file__).parent / "GUIDE.md"

_AREA_LIST_PARAMETERS = vol.Schema(
    {
        vol.Optional("area_id"): str,
        vol.Optional("area-id"): str,
        vol.Optional("floor"): str,
        vol.Optional("count", default=False): bool,
        vol.Optional("brief", default=False): bool,
        vol.Optional("limit", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

_DEVICE_LIST_PARAMETERS = vol.Schema(
    {
        vol.Optional("device_id"): str,
        vol.Optional("device-id"): str,
        vol.Optional("area"): str,
        vol.Optional("floor"): str,
        vol.Optional("count", default=False): bool,
        vol.Optional("brief", default=False): bool,
        vol.Optional("limit", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

_ENTITY_LIST_PARAMETERS = vol.Schema(
    {
        vol.Optional("entity_id"): str,
        vol.Optional("entity-id"): str,
        vol.Optional("domain"): str,
        vol.Optional("area"): str,
        vol.Optional("floor"): str,
        vol.Optional("label"): str,
        vol.Optional("device"): str,
        vol.Optional("device_class"): str,
        vol.Optional("device-class"): str,
        vol.Optional("count", default=False): bool,
        vol.Optional("brief", default=False): bool,
        vol.Optional("limit", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)


def _tool_str(data: dict[str, Any], *keys: str) -> str | None:
    """Extract a string value from alternate parameter names."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str):
            return value
    return None


def _entity_device_class(
    reg_entry: er.RegistryEntry | None, attributes: dict[str, Any]
) -> str:
    """Resolve device class with the same precedence as hab entity list."""
    if reg_entry and reg_entry.original_device_class:
        return reg_entry.original_device_class
    if reg_entry and reg_entry.device_class:
        return reg_entry.device_class
    device_class = attributes.get("device_class")
    if isinstance(device_class, str):
        return device_class
    return ""


def _apply_limit(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Apply list limit the same way as hab list commands."""
    if limit > 0 and len(items) > limit:
        return items[:limit]
    return items


async def build_generation_instructions(hass: HomeAssistant, prompt: str) -> str:
    """Build instructions used for Lovelace dashboard generation."""
    guide = await hass.async_add_executor_job(GENERATE_GUIDELINES.read_text)

    return (
        "Generate a Home Assistant Lovelace dashboard configuration.\n"
        "Return only valid JSON (no markdown and no explanation).\n"
        "Return a complete dashboard object with a top-level `views` array.\n"
        "Each view should include useful cards for the user request.\n"
        "Use the list tools to discover real area, device and entity IDs.\n"
        "Use real entity IDs discovered from available tools.\n"
        "Prioritize readable, practical dashboards over decorative layouts.\n\n"
        f"User request:\n{prompt.strip()}\n\n"
        f"{guide}"
    )


class AreaListTool(llm.Tool):
    """Tool mirroring `hab area list`."""

    name = "area_list"
    description = (
        "List areas with hab-compatible filters: area-id, floor, count, brief, limit."
    )
    parameters = _AREA_LIST_PARAMETERS

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the tool."""
        self._hass = hass

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """List areas with hab-compatible output fields."""
        del hass, llm_context
        data = cast(dict[str, Any], self.parameters(tool_input.tool_args))
        area_id_filter = _tool_str(data, "area_id", "area-id")
        floor_filter = _tool_str(data, "floor")
        count = cast(bool, data["count"])
        brief = cast(bool, data["brief"])
        limit = cast(int, data["limit"])

        area_registry = ar.async_get(self._hass)

        result: list[dict[str, Any]] = []
        for area in area_registry.areas.values():
            if area_id_filter and area.id != area_id_filter:
                continue
            if floor_filter and area.floor_id != floor_filter:
                continue
            result.append(
                {
                    "area_id": area.id,
                    "name": area.name,
                    "floor_id": area.floor_id,
                    "icon": area.icon,
                    "labels": sorted(area.labels),
                }
            )

        if count:
            return {"count": len(result)}

        result = _apply_limit(result, limit)
        if brief:
            return {
                "areas": [
                    {"area_id": area["area_id"], "name": area["name"]}
                    for area in result
                ]
            }
        return {"areas": result}


class DeviceListTool(llm.Tool):
    """Tool mirroring `hab device list`."""

    name = "device_list"
    description = (
        "List devices with hab-compatible filters: device-id, area, floor, count,"
        " brief, limit."
    )
    parameters = _DEVICE_LIST_PARAMETERS

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the tool."""
        self._hass = hass

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """List devices with hab-compatible output fields."""
        del hass, llm_context
        data = cast(dict[str, Any], self.parameters(tool_input.tool_args))
        device_id_filter = _tool_str(data, "device_id", "device-id")
        area_filter = _tool_str(data, "area")
        floor_filter = _tool_str(data, "floor")
        count = cast(bool, data["count"])
        brief = cast(bool, data["brief"])
        limit = cast(int, data["limit"])

        area_floor_map: dict[str, str] = {}
        if floor_filter:
            area_registry = ar.async_get(self._hass)
            area_floor_map = {
                area.id: area.floor_id or ""
                for area in area_registry.areas.values()
                if area.id
            }

        device_registry = dr.async_get(self._hass)
        result: list[dict[str, Any]] = []
        for device in device_registry.devices.values():
            if device_id_filter and device.id != device_id_filter:
                continue
            if area_filter and device.area_id != area_filter:
                continue
            if floor_filter:
                if not device.area_id:
                    continue
                if area_floor_map.get(device.area_id) != floor_filter:
                    continue
            result.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "area_id": device.area_id,
                }
            )

        if count:
            return {"count": len(result)}

        result = _apply_limit(result, limit)
        if brief:
            return {
                "devices": [{"id": item["id"], "name": item["name"]} for item in result]
            }
        return {"devices": result}


class EntityListTool(llm.Tool):
    """Tool mirroring `hab entity list`."""

    name = "entity_list"
    description = (
        "List entities with hab-compatible filters: entity-id, domain, area, floor,"
        " label, device, device-class, count, brief, limit."
    )
    parameters = _ENTITY_LIST_PARAMETERS

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the tool."""
        self._hass = hass

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """List entities with hab-compatible output fields."""
        del hass, llm_context
        data = cast(dict[str, Any], self.parameters(tool_input.tool_args))
        entity_id_filter = _tool_str(data, "entity_id", "entity-id")
        domain_filter = _tool_str(data, "domain")
        area_filter = _tool_str(data, "area")
        floor_filter = _tool_str(data, "floor")
        label_filter = _tool_str(data, "label")
        device_filter = _tool_str(data, "device")
        device_class_filter = _tool_str(data, "device_class", "device-class")
        count = cast(bool, data["count"])
        brief = cast(bool, data["brief"])
        limit = cast(int, data["limit"])

        area_floor_map: dict[str, str] = {}
        if floor_filter:
            area_registry = ar.async_get(self._hass)
            area_floor_map = {
                area.id: area.floor_id or ""
                for area in area_registry.areas.values()
                if area.id
            }

        entity_registry = er.async_get(self._hass)

        result: list[dict[str, Any]] = []
        for state in self._hass.states.async_all():
            entity_id = state.entity_id

            if entity_id_filter and entity_id != entity_id_filter:
                continue

            if domain_filter and state.domain != domain_filter:
                continue

            reg_entry = entity_registry.async_get(entity_id)

            if device_filter:
                if reg_entry is None or reg_entry.device_id != device_filter:
                    continue

            if area_filter:
                if reg_entry is None or reg_entry.area_id != area_filter:
                    continue

            if floor_filter:
                if reg_entry is None or not reg_entry.area_id:
                    continue
                if area_floor_map.get(reg_entry.area_id) != floor_filter:
                    continue

            if label_filter:
                if reg_entry is None or label_filter not in reg_entry.labels:
                    continue

            friendly_name = state.attributes.get("friendly_name")
            if not isinstance(friendly_name, str):
                friendly_name = ""

            device_class = _entity_device_class(reg_entry, state.attributes)
            if device_class_filter and device_class != device_class_filter:
                continue

            result.append(
                {
                    "entity_id": entity_id,
                    "state": state.state,
                    "name": friendly_name,
                    "area_id": reg_entry.area_id if reg_entry else "",
                    "device_id": reg_entry.device_id if reg_entry else "",
                    "device_class": device_class,
                    "labels": sorted(reg_entry.labels) if reg_entry else [],
                    "disabled": reg_entry.disabled_by is not None
                    if reg_entry
                    else False,
                }
            )

        if count:
            return {"count": len(result)}

        result = _apply_limit(result, limit)
        if brief:
            return {
                "entities": [
                    {"entity_id": item["entity_id"], "name": item["name"]}
                    for item in result
                ]
            }
        return {"entities": result}


class LovelaceDashboardGenerationAPI(llm.API):
    """LLM API for Lovelace dashboard generation."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API."""
        super().__init__(hass=hass, id=API_ID, name=API_NAME)

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the API instance."""
        return llm.APIInstance(
            api=self,
            api_prompt=API_PROMPT,
            llm_context=llm_context,
            tools=[
                AreaListTool(self.hass),
                DeviceListTool(self.hass),
                EntityListTool(self.hass),
            ],
        )
