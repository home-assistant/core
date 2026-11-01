"""Select platform for Lutron GRAFIK Eye."""

from typing import override

from grafikeye import GrafikEyeController

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GrafikEyeConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrafikEyeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lutron GRAFIK Eye scene selectors."""
    controller = entry.runtime_data
    scenes = await controller.get_active_scenes()

    async_add_entities(
        GrafikEyeSceneSelect(
            controller=controller,
            entry_id=entry.entry_id,
            unit_id=unit_id,
            scene=scene,
        )
        for unit_id, scene in scenes.items()
    )


class GrafikEyeSceneSelect(SelectEntity):
    """Scene selector for a Lutron GRAFIK Eye control unit."""

    _attr_has_entity_name = True
    _attr_name = "Scene"
    _attr_options = [str(scene) for scene in range(17)]

    def __init__(
        self,
        controller: GrafikEyeController,
        entry_id: str,
        unit_id: int,
        scene: int,
    ) -> None:
        """Initialize the scene selector."""
        self._controller = controller
        self._unit_id = unit_id

        self._attr_unique_id = f"{entry_id}_{unit_id}_scene"
        self._attr_current_option = str(scene)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{unit_id}")},
            name=f"GRAFIK Eye Control Unit {unit_id}",
            manufacturer="Lutron",
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Register scene updates."""
        self.async_on_remove(
            self._controller.register_scene_callback(
                self._unit_id,
                self._scene_changed,
            )
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Select a scene."""
        self._controller.select_scene(
            int(option),
            self._unit_id,
        )

        self._attr_current_option = option
        self.async_write_ha_state()

    @callback
    def _scene_changed(self, scene: int) -> None:
        """Handle scene changes."""
        self._attr_current_option = str(scene)
        self.async_write_ha_state()
