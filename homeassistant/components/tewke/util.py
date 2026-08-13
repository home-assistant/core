"""Utilities for the Tewke integration."""

from typing import TYPE_CHECKING

from pytewke.error import PyTewkeObserveError

from homeassistant.const import CONF_NAME
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DISPATCHER_ADD_SCENES, DOMAIN, LOGGER

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


class _TewkeObserver:
    """Observer for Tewke device callbacks."""

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        hass: HomeAssistant,
        entry: TewkeConfigEntry,
    ) -> None:
        """Initialize the observer."""
        self.coordinator = coordinator
        self.hass = hass
        self.entry = entry

    def on_scene_update(self, scenes: dict[str, Scene]) -> None:
        """Handle scene updates from the Tewke device.

        This callback is triggered when the scenes on the device change.
        It identifies new scenes, automatically adds them to the integration,
        and removes deleted scenes.
        """
        self.coordinator.reset_observation_timeout()
        current_scenes = self.coordinator.data["scenes"]

        # Handle scenes that are no longer provided by the device
        removed_configured_ids = [sid for sid in current_scenes if sid not in scenes]
        if removed_configured_ids:
            LOGGER.info("Removing deleted scenes: %s", removed_configured_ids)

            ent_reg = er.async_get(self.hass)
            config_data = self.coordinator.data["config"]
            if config_data:
                hardware_id = config_data.hardware_id
                for sid in removed_configured_ids:
                    unique_id = f"{hardware_id}_{sid}"
                    entity_id = ent_reg.async_get_entity_id("light", DOMAIN, unique_id)
                    if entity_id:
                        ent_reg.async_remove(entity_id)

        # Add new scenes
        new_scenes = {
            scene_id: scene
            for scene_id, scene in scenes.items()
            if scene_id not in current_scenes
        }

        if new_scenes:
            LOGGER.info("Discovered new scenes, automatically adding: %s", new_scenes)
            self.coordinator.async_set_updated_data(
                {
                    **self.coordinator.data,
                    "scenes": dict(scenes),
                }
            )
            async_dispatcher_send(
                self.hass,
                f"{DISPATCHER_ADD_SCENES}_{self.entry.entry_id}",
                list(new_scenes.values()),
            )
            return

        self.coordinator.async_set_updated_data(
            {
                **self.coordinator.data,
                "scenes": dict(scenes),
            }
        )

    def on_target_update(self, targets: dict[int, Target]) -> None:
        """Handle target updates from the Tewke device.

        This callback is triggered when the targets on the device change.
        It updates the coordinator with the new target data.
        """
        self.coordinator.reset_observation_timeout()
        self.coordinator.async_set_updated_data(
            {
                **self.coordinator.data,
                "targets": targets,
            }
        )

    def on_sensor_update(self, sensor_data: SensorData) -> None:
        """Handle sensor updates from the Tewke device.

        This callback is triggered when the sensors on the device change.
        """
        self.coordinator.reset_observation_timeout()
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, "sensors": sensor_data}
        )

    def on_radar_update(self, radar_data: RadarData) -> None:
        """Handle radar updates from the Tewke device.

        This callback is triggered when the radar on the device changes.
        """
        self.coordinator.reset_observation_timeout()
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, "radar": radar_data}
        )

    def on_energy_update(self, energy_data: EnergyData) -> None:
        """Handle energy updates from the Tewke device.

        This callback is triggered when the energy on the device changes.
        """
        self.coordinator.reset_observation_timeout()
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, "energy": energy_data}
        )

    def on_config_update(self, config_data: ConfigData) -> None:
        """Handle config updates from the Tewke device.

        This callback is triggered when the config on the device changes.
        """
        self.coordinator.reset_observation_timeout()
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, "config": config_data}
        )
        device_registry = dr.async_get(self.hass)
        tap = self.entry.runtime_data.tap
        device_id = tap.wall_dock_id
        if device_id is None:
            return

        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, device_id), self.entry.entry_id
        )

        if device:
            new_name = config_data.device_name
            if new_name and new_name != self.entry.data.get(CONF_NAME):
                LOGGER.debug("Device renamed to %r, updating HA", new_name)
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    title=new_name,
                    data={**self.entry.data, CONF_NAME: new_name},
                )
                device_registry.async_update_device(device.id, name=new_name)

            new_version = config_data.tewke_os_version
            if new_version and new_version != device.sw_version:
                LOGGER.debug("Device updated to %r, updating HA", new_version)
                device_registry.async_update_device(device.id, sw_version=new_version)


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
    await tap.close_observations()

    observer = _TewkeObserver(coordinator, hass, entry)

    try:
        LOGGER.debug(
            "Setting up CoAP observations for %s",
            entry.data.get(CONF_NAME, entry.entry_id),
        )
        await tap.observe(
            scene_callback=observer.on_scene_update,
            target_callback=observer.on_target_update,
            sensor_callback=observer.on_sensor_update,
            radar_callback=observer.on_radar_update,
            energy_callback=observer.on_energy_update,
            config_change_callback=observer.on_config_update,
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

    return True
