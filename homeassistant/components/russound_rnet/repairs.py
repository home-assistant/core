"""Repairs for the Russound RNET integration."""

from __future__ import annotations

from contextlib import suppress
import json
from typing import Any

from aiorussound import RussoundTcpConnectionHandler
from aiorussound.rnet.client import RussoundRNETClient
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_CONTROLLERS,
    CONF_SOURCES,
    CONF_ZONES,
    DOMAIN,
    RNET_EXCEPTIONS,
    RNET_MODELS,
    TYPE_TCP,
)

ISSUE_YAML_IMPORT = "yaml_import_needed"
ISSUE_DEPRECATED_YAML = "deprecated_yaml"


@callback
def async_create_yaml_import_issue(
    hass: HomeAssistant, yaml_config: dict[str, Any]
) -> None:
    """Create a fixable repair issue to complete YAML import."""
    # Serialize nested config as JSON since issue data values must be scalar
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_YAML_IMPORT,
        breaks_in_ha_version="2026.11",
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_YAML_IMPORT,
        data={"yaml_config_json": json.dumps(yaml_config, default=str)},
    )


@callback
def async_create_deprecated_yaml_issue(hass: HomeAssistant) -> None:
    """Create a non-fixable repair issue to remove YAML config."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_DEPRECATED_YAML,
        breaks_in_ha_version="2026.11",
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_DEPRECATED_YAML,
    )


class YamlImportRepairFlow(RepairsFlow):
    """Repair flow to complete YAML import with model/sources/zones selection."""

    def __init__(self, yaml_config: dict[str, Any]) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self._yaml_config = yaml_config
        self._data: dict[str, Any] = {}
        self._raw_zones: dict[int, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the init step — validate connection and show confirm."""
        host = str(self._yaml_config.get(CONF_HOST, ""))
        port = int(self._yaml_config.get(CONF_PORT, 0))

        # Validate connection first
        client = RussoundRNETClient(RussoundTcpConnectionHandler(host, port))
        try:
            await client.connect()
            await client.get_all_zone_info(1, 1)
        except RNET_EXCEPTIONS:
            return self.async_abort(reason="cannot_connect")
        finally:
            with suppress(*RNET_EXCEPTIONS):
                await client.disconnect()

        # Parse YAML sources and zones
        yaml_sources = self._yaml_config.get("sources", [])
        sources = {
            str(i + 1): src.get(CONF_NAME, "")
            for i, src in enumerate(yaml_sources)
            if src.get(CONF_NAME, "").strip()
        }

        yaml_zones = self._yaml_config.get("zones", {})
        # Store raw YAML zone data; convert to controller_zone format after model selection
        raw_zones: dict[int, str] = {}
        for zone_id, zone_data in yaml_zones.items():
            name = zone_data.get(CONF_NAME, "").strip()
            if name:
                raw_zones[int(zone_id)] = name

        self._data = {
            CONF_TYPE: TYPE_TCP,
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SOURCES: sources,
        }
        self._raw_zones = raw_zones

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Show confirmation before proceeding with import."""
        if user_input is not None:
            return await self.async_step_model()

        return self.async_show_form(step_id="confirm")

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle model selection."""
        if user_input is not None:
            self._data[CONF_MODEL] = user_input[CONF_MODEL]
            return await self.async_step_sources()

        model_schema = vol.Schema(
            {
                vol.Required(CONF_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=key, label=model.name)
                            for key, model in RNET_MODELS.items()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="model",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="model", data_schema=model_schema)

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle source name configuration."""
        model = RNET_MODELS[self._data[CONF_MODEL]]

        if user_input is not None:
            sources = {
                str(i): name
                for i in range(1, model.max_sources + 1)
                if (name := user_input.get(f"source_{i}", "").strip())
            }
            self._data[CONF_SOURCES] = sources
            return await self.async_step_zones()

        existing_sources = self._data.get(CONF_SOURCES, {})
        source_schema = vol.Schema(
            {
                vol.Optional(
                    f"source_{i}",
                    default=existing_sources.get(str(i), ""),
                ): TextSelector()
                for i in range(1, model.max_sources + 1)
            }
        )
        return self.async_show_form(step_id="sources", data_schema=source_schema)

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle zone name configuration."""
        model = RNET_MODELS[self._data[CONF_MODEL]]

        # Convert raw YAML zone IDs to controller_zone format using model's max_zones
        existing_zones: dict[str, str] = {}
        for zid, name in self._raw_zones.items():
            controller_id = (zid - 1) // model.max_zones + 1
            local_zone_id = (zid - 1) % model.max_zones + 1
            existing_zones[f"{controller_id}_{local_zone_id}"] = name

        # Determine number of controllers from converted zones
        if existing_zones:
            num_controllers = min(
                max(int(key.split("_")[0]) for key in existing_zones),
                model.max_controllers,
            )
        else:
            num_controllers = 1

        if user_input is not None:
            zones = {
                f"{c}_{z}": name
                for c in range(1, num_controllers + 1)
                for z in range(1, model.max_zones + 1)
                if (name := user_input.get(f"zone_{c}_{z}", "").strip())
            }
            self._data[CONF_ZONES] = zones
            self._data[CONF_CONTROLLERS] = num_controllers

            # Create config entry via config flow
            result = await self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=self._data,
            )
            if result.get("type") != "create_entry":
                return self.async_abort(reason="import_failed")

            # Now prompt user to remove YAML
            async_create_deprecated_yaml_issue(self.hass)
            return self.async_create_entry(data={})

        zone_schema = vol.Schema(
            {
                vol.Optional(
                    f"zone_{c}_{z}",
                    default=existing_zones.get(f"{c}_{z}", ""),
                ): TextSelector()
                for c in range(1, num_controllers + 1)
                for z in range(1, model.max_zones + 1)
            }
        )
        return self.async_show_form(step_id="zones", data_schema=zone_schema)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == ISSUE_YAML_IMPORT:
        assert data is not None
        yaml_config = json.loads(str(data["yaml_config_json"]))
        return YamlImportRepairFlow(yaml_config=yaml_config)

    raise ValueError(f"unknown repair {issue_id}")  # pragma: no cover
