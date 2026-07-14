"""Repairs for the Tewke integration."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.data_entry_flow import section
from homeassistant.helpers import issue_registry as ir, selector
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_DEFAULT_SCENE_FAN_DIMMING,
    CONF_DISABLED_SCENES,
    DEFAULT_SCENE_FAN_DIMMING,
    DISPATCHER_ADD_SCENES,
    DOMAIN,
    LOGGER,
)
from .util import _get_default_scene_fan_dimming

if TYPE_CHECKING:
    from pytewke.data import Scene

    from homeassistant.core import HomeAssistant
    from homeassistant.data_entry_flow import FlowResult

    from .data import TewkeConfigEntry

_CONTROL_TYPE_OPTIONS = [
    selector.SelectOptionDict(value="light", label="Light"),
    selector.SelectOptionDict(value="switch", label="Switch"),
    selector.SelectOptionDict(value="fan", label="Fan"),
]

_CONTROL_TYPE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=_CONTROL_TYPE_OPTIONS,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

_FAN_SPEED_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=1,
        max=100,
        step=1,
        mode=selector.NumberSelectorMode.SLIDER,
    )
)

# Maximum scenes handled in one batch step;
# must match the scene_N entries in strings.json.
_MAX_BATCH_SCENES = 50


class TewkeNewSceneRepairFlow(RepairsFlow):
    """Flow to configure pending scenes for a device, up to one batch per invocation."""

    def __init__(self, entry: TewkeConfigEntry) -> None:
        """Initialise the flow."""
        self.entry = entry
        self._pending_list: list[tuple[str, Scene]] = []
        self._pending_scene_config: dict[str, dict[str, str | bool]] | None = None
        self._new_fan_scenes: list[tuple[str, Scene]] = []

    async def async_step_init(
        self, _user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Load pending scenes and hand off to the batch configuration step."""
        pending: dict[str, Scene] = (
            self.entry.runtime_data.pending_scenes
            if hasattr(self.entry, "runtime_data")
            else {}
        )

        if not pending:
            return self.async_abort(reason="no_new_scenes")

        self._pending_list = list(pending.items())[:_MAX_BATCH_SCENES]
        return await self.async_step_configure_scenes()

    async def async_step_configure_scenes(
        self, user_input: dict[str, dict[str, str | bool]] | None = None
    ) -> FlowResult:
        """Show a single form with one dropdown per pending scene."""
        if user_input is not None:
            self._new_fan_scenes = [
                self._pending_list[i]
                for i in range(len(self._pending_list))
                if user_input.get(f"scene_section_{i}", {}).get("scene_text") == "fan"
                and user_input.get(f"scene_section_{i}", {}).get("enabled_text") is True
            ]
            if len(self._new_fan_scenes) > 0:
                self._pending_scene_config = user_input
                return await self.async_step_fan_default_speeds()
            return await self._async_apply_results(user_input)

        # Re-filter against current pending_scenes to drop any externally removed scenes
        pending: dict[str, Scene] = (
            self.entry.runtime_data.pending_scenes
            if hasattr(self.entry, "runtime_data")
            else {}
        )
        self._pending_list = [
            (sid, scene) for sid, scene in self._pending_list if sid in pending
        ]

        if not self._pending_list:
            return self.async_abort(reason="no_new_scenes")

        fields: dict = {}
        placeholders: dict[str, str] = {"name": self.entry.title}
        for i, (_, scene) in enumerate(self._pending_list):
            fields[vol.Required(f"scene_section_{i}")] = section(
                vol.Schema(
                    {
                        vol.Optional(
                            "enabled_text", default=True
                        ): selector.BooleanSelector(),
                        vol.Required(
                            "scene_text", default="light"
                        ): _CONTROL_TYPE_SELECTOR,
                    }
                )
            )
            placeholders[f"scene_section_{i}"] = scene.name

        return self.async_show_form(
            step_id="configure_scenes",
            data_schema=vol.Schema(fields),
            description_placeholders=placeholders,
        )

    async def async_step_fan_default_speeds(
        self, user_input: dict[str, float] | None = None
    ) -> FlowResult:
        """Set a default speed value for each newly configured fan scene."""
        if user_input is not None:
            index_name_to_id = {
                f"fan_scene_{i}": sid for i, (sid, _) in enumerate(self._new_fan_scenes)
            }
            scene_configs = user_input.items()

            fan_dimming = {
                index_name_to_id[index_name]: int(fan_speed)
                for index_name, fan_speed in scene_configs
                if index_name in index_name_to_id
            }

            return await self._async_apply_results(
                self._pending_scene_config or {}, fan_dimming
            )

        fields: dict = {}
        placeholders: dict[str, str] = {"name": self.entry.title}
        for i, (_, scene) in enumerate(self._new_fan_scenes):
            fields[
                vol.Required(f"fan_scene_{i}", default=DEFAULT_SCENE_FAN_DIMMING)
            ] = _FAN_SPEED_SELECTOR
            placeholders[f"fan_scene_{i}"] = scene.name

        return self.async_show_form(
            step_id="fan_default_speeds",
            data_schema=vol.Schema(fields),
            description_placeholders=placeholders,
        )

    async def _async_apply_results(
        self,
        user_input: dict[str, dict[str, str | bool]],
        fan_dimming: dict[str, int] | None = None,
    ) -> FlowResult:
        """Commit all configured scene control types and update HA state."""
        pending: dict[str, Scene] = self.entry.runtime_data.pending_scenes
        new_control_types = self.entry.runtime_data.scene_control_types.copy()
        added_scenes: list[Scene] = []
        newly_disabled = []
        index_name_to_id = {
            f"scene_section_{i}": sid for i, (sid, _) in enumerate(self._pending_list)
        }
        scene_configs = user_input.items()

        for index_name, config in scene_configs:
            if index_name not in index_name_to_id:
                continue

            if not isinstance(config, dict):
                continue

            scene_text = config.get("scene_text")
            enabled_text = config.get("enabled_text", True)
            if not isinstance(scene_text, str) or not isinstance(enabled_text, bool):
                continue

            scene_id = index_name_to_id[index_name]
            if scene_id not in pending:
                LOGGER.warning("Scene %s no longer pending; skipping", scene_id)
                continue

            added_scenes.append(pending[scene_id])

            new_control_types[scene_id] = scene_text
            if not enabled_text:
                newly_disabled.append(scene_id)

            del pending[scene_id]

        existing_disabled: list[str] = list(
            self.entry.data.get(CONF_DISABLED_SCENES, [])
        )
        merged_disabled = existing_disabled + [
            sid for sid in newly_disabled if sid not in existing_disabled
        ]

        existing_fan_dimming = _get_default_scene_fan_dimming(self.entry)
        merged_fan_dimming = {**existing_fan_dimming, **(fan_dimming or {})}

        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                "scene_control_types": new_control_types,
                CONF_DISABLED_SCENES: merged_disabled,
                CONF_DEFAULT_SCENE_FAN_DIMMING: merged_fan_dimming,
            },
        )
        self.entry.runtime_data.scene_control_types = new_control_types

        coordinator = self.entry.runtime_data.coordinator
        scenes_all = coordinator.data.get("scenes_all", {})
        configured_scenes = {
            sid: scene for sid, scene in scenes_all.items() if sid in new_control_types
        }
        coordinator.async_set_updated_data(
            {
                **coordinator.data,
                "scenes": configured_scenes,
            }
        )

        if added_scenes:
            async_dispatcher_send(self.hass, DISPATCHER_ADD_SCENES, added_scenes)

        if not pending:
            ir.async_delete_issue(
                self.hass, DOMAIN, f"new_scenes_found_{self.entry.entry_id}"
            )

        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> TewkeNewSceneRepairFlow | None:
    """Create a repair flow to configure new scenes."""
    if issue_id.startswith("new_scenes_found"):
        if data is None:
            return None
        entry_id = data.get("entry_id")
        if not isinstance(entry_id, str):
            return None

        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return None

        return TewkeNewSceneRepairFlow(entry)
    LOGGER.warning("Unhandled issue ID %s", issue_id)
    return None
