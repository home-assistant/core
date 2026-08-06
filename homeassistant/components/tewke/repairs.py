"""Repairs for the Tewke integration."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DISPATCHER_ADD_SCENES, DOMAIN, LOGGER

if TYPE_CHECKING:
    from pytewke.data import Scene

    from homeassistant.core import HomeAssistant
    from homeassistant.data_entry_flow import FlowResult

    from .data import TewkeConfigEntry


class TewkeNewSceneRepairFlow(RepairsFlow):
    """Flow to configure pending scenes for a device."""

    def __init__(self, entry: TewkeConfigEntry) -> None:
        """Initialise the flow."""
        self.entry = entry
        self._pending_list: list[tuple[str, Scene]] = []
        self._pending_scene_config: dict[str, dict[str, str | bool]] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Load pending scenes and show a confirmation form."""
        pending: dict[str, Scene] = (
            self.entry.runtime_data.pending_scenes
            if hasattr(self.entry, "runtime_data")
            else {}
        )

        if not pending:
            return self.async_abort(
                reason="no_new_scenes",
                description_placeholders={"name": self.entry.title},
            )

        if user_input is not None:
            return await self._async_apply_results()

        self._pending_list = list(pending.items())
        scene_list = "\n".join(f"- {scene.name}" for _, scene in self._pending_list)

        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "name": self.entry.title,
                "scene_list": scene_list,
            },
        )

    async def _async_apply_results(
        self,
    ) -> FlowResult:
        """Commit all configured scenes and update HA state."""
        pending: dict[str, Scene] = self.entry.runtime_data.pending_scenes
        current_scenes = self.entry.runtime_data.scenes.copy()
        added_scenes: list[Scene] = []

        for scene_id, _ in self._pending_list:
            if scene_id not in pending:
                LOGGER.warning("Scene %s no longer pending; skipping", scene_id)
                continue

            added_scenes.append(pending[scene_id])
            current_scenes[scene_id] = pending[scene_id]
            del pending[scene_id]

        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                "scenes": current_scenes,
            },
        )

        coordinator = self.entry.runtime_data.coordinator
        if coordinator.data is not None:
            scenes_all = coordinator.data.get("scenes_all", {})
            configured_scenes = {
                sid: scene for sid, scene in scenes_all.items() if sid in current_scenes
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
