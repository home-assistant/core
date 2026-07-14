"""Utilities for the Tewke integration."""

from typing import TYPE_CHECKING

from pytewke.error import PyTewkeObserveError

from homeassistant.const import CONF_NAME
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import CONF_DEFAULT_SCENE_FAN_DIMMING, CONF_DISABLED_SCENES, DOMAIN, LOGGER

if TYPE_CHECKING:
    from pytewke.data import (
        ConfigData,
        EnergyData,
        RadarData,
        Scene,
        SensorData,
        Target,
    )

    from homeassistant.core import HomeAssistant

    from .coordinator import TewkeCoordinator
    from .data import TewkeConfigEntry


def _get_default_scene_fan_dimming(entry: TewkeConfigEntry) -> dict[str, int]:
    """Return per-scene fan dimming defaults, preferring options over initial data."""
    return entry.options.get(CONF_DEFAULT_SCENE_FAN_DIMMING) or entry.data.get(
        CONF_DEFAULT_SCENE_FAN_DIMMING, {}
    )


def _tewke_to_ha_brightness(value: int) -> int:
    """Convert a Tewke brightness (0-100) to HA brightness (0-255).

    The input value is clamped to the range [0, 100].
    """
    value = max(0, min(100, value))
    return round(value / 100 * 255)


def _ha_to_tewke_brightness(value: int) -> int:
    """Convert a HA brightness (0-255) to a Tewke brightness (0-100).

    The input value is clamped to the range [0, 255].
    """
    value = max(0, min(255, value))
    return round(value / 255 * 100)


async def async_setup_observe(
    coordinator: TewkeCoordinator,
    hass: HomeAssistant,
    entry: TewkeConfigEntry,
) -> bool:
    """Register CoAP observation callbacks on the Tap and start observing.

    Returns True if observe was set up successfully, False otherwise.
    The ``observe_active`` flag on ``entry.runtime_data`` is set accordingly.
    """
    tap = entry.runtime_data.tap

    tap.clear_callbacks()
    await tap._observation_manager.close()  # noqa: SLF001

    def _on_scene_update(scenes: dict[str, Scene]) -> None:
        """Handle scene updates from the Tewke device.

        This callback is triggered when the scenes on the device change. It
        identifies new scenes and creates a repair issue to configure them.
        """
        coordinator.reset_observation_timeout()
        if coordinator.data is None:
            return

        scene_control_types = entry.runtime_data.scene_control_types

        # Handle scenes that are no longer provided by the device
        removed_configured_ids = [
            sid for sid in scene_control_types if sid not in scenes
        ]
        if removed_configured_ids:
            LOGGER.info(
                "Marking deleted scenes as unavailable: %s", removed_configured_ids
            )
            new_scene_control_types = dict(scene_control_types)

            for sid in removed_configured_ids:
                del new_scene_control_types[sid]

            new_data = dict(entry.data)
            new_data["scene_control_types"] = new_scene_control_types

            if CONF_DISABLED_SCENES in new_data:
                new_data[CONF_DISABLED_SCENES] = [
                    sid
                    for sid in new_data[CONF_DISABLED_SCENES]
                    if sid not in removed_configured_ids
                ]
            if CONF_DEFAULT_SCENE_FAN_DIMMING in new_data:
                new_fan_dimming = dict(new_data[CONF_DEFAULT_SCENE_FAN_DIMMING])
                for sid in removed_configured_ids:
                    new_fan_dimming.pop(sid, None)
                new_data[CONF_DEFAULT_SCENE_FAN_DIMMING] = new_fan_dimming

            entry.runtime_data.scene_control_types = new_scene_control_types
            hass.config_entries.async_update_entry(entry, data=new_data)
            return

        configured_scenes = {
            scene_id: scene
            for scene_id, scene in scenes.items()
            if scene_id in scene_control_types
        }

        coordinator.async_set_updated_data(
            {
                **coordinator.data,
                "scenes": configured_scenes,
                "scenes_all": scenes,
            }
        )

        # Remove pending scenes that no longer exist on the device
        stale_ids = [
            sid for sid in entry.runtime_data.pending_scenes if sid not in scenes
        ]
        for sid in stale_ids:
            del entry.runtime_data.pending_scenes[sid]

        new_scenes = {
            scene_id: scene
            for scene_id, scene in scenes.items()
            if scene_id not in scene_control_types
            and scene_id not in entry.runtime_data.pending_scenes
        }

        if not new_scenes and not entry.runtime_data.pending_scenes:
            ir.async_delete_issue(hass, DOMAIN, f"new_scenes_found_{entry.entry_id}")

        if new_scenes:
            LOGGER.info("Discovered new scenes, pending configuration: %s", new_scenes)
            entry.runtime_data.pending_scenes.update(new_scenes)
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"new_scenes_found_{entry.entry_id}",
                data={"entry_id": entry.entry_id},
                is_fixable=True,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="new_scenes_found",
                translation_placeholders={"name": entry.title},
            )

    def _on_target_update(targets: dict[int, Target]) -> None:
        """Handle target updates from the Tewke device.

        This callback is triggered when the targets on the device change.
        It updates the coordinator with the new target data.
        """
        coordinator.reset_observation_timeout()
        if coordinator.data is None:
            return

        coordinator.async_set_updated_data(
            {
                **coordinator.data,
                "targets": targets,
            }
        )

    def _on_sensor_update(sensor_data: SensorData) -> None:
        """Handle sensor updates from the Tewke device.

        This callback is triggered when the sensors on the device change.
        """
        coordinator.reset_observation_timeout()
        if coordinator.data is None:
            return
        coordinator.async_set_updated_data({**coordinator.data, "sensors": sensor_data})

    def _on_radar_update(radar_data: RadarData) -> None:
        """Handle radar updates from the Tewke device.

        This callback is triggered when the radar on the device changes.
        """
        coordinator.reset_observation_timeout()
        if coordinator.data is None:
            return
        coordinator.async_set_updated_data({**coordinator.data, "radar": radar_data})

    def _on_energy_update(energy_data: EnergyData) -> None:
        """Handle energy updates from the Tewke device.

        This callback is triggered when the energy on the device changes.
        """
        coordinator.reset_observation_timeout()
        if coordinator.data is None:
            return
        coordinator.async_set_updated_data({**coordinator.data, "energy": energy_data})

    def _on_config_update(config_data: ConfigData) -> None:
        """Handle config updates from the Tewke device.

        This callback is triggered when the config on the device changes.
        """
        coordinator.reset_observation_timeout()
        if coordinator.data is None:
            return
        coordinator.async_set_updated_data({**coordinator.data, "config": config_data})
        device_registry = dr.async_get(hass)
        device_id = tap.wall_dock_id
        device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})

        if device:
            new_name = config_data.device_name
            if new_name and new_name != entry.data.get(CONF_NAME):
                LOGGER.debug("Device renamed to %r, updating HA", new_name)
                hass.config_entries.async_update_entry(
                    entry,
                    title=new_name,
                    data={**entry.data, CONF_NAME: new_name},
                )
                device_registry.async_update_device(device.id, name=new_name)

            new_version = config_data.tewke_os_version
            if new_version and new_version != device.sw_version:
                LOGGER.debug("Device updated to %r, updating HA", new_version)
                device_registry.async_update_device(device.id, sw_version=new_version)

    try:
        LOGGER.debug(
            "Setting up CoAP observations for %s",
            entry.data.get(CONF_NAME, entry.entry_id),
        )
        await tap.observe(
            scene_callback=_on_scene_update,
            target_callback=_on_target_update,
            sensor_callback=_on_sensor_update,
            radar_callback=_on_radar_update,
            energy_callback=_on_energy_update,
            config_change_callback=_on_config_update,
        )
    except PyTewkeObserveError:
        LOGGER.warning(
            "Failed to set up CoAP observations for %s; will retry on next poll",
            entry.data.get(CONF_NAME, entry.entry_id),
            exc_info=True,
        )
        entry.runtime_data.observe_active = False
        coordinator.reset_observation_timeout()
        return False

    entry.runtime_data.observe_active = True
    coordinator.reset_observation_timeout()

    # Process scenes already fetched during initial discovery
    if coordinator.data and "scenes_all" in coordinator.data:
        _on_scene_update(coordinator.data["scenes_all"])

    return True
