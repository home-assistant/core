"""Entities exposing active Hue scene information per group.

These sensors mirror the naming pattern of Hue scene entities: the entity_id
is prefixed with the Hue group (room / zone) name while the displayed name in
the UI is just the short per-entity portion.
"""

from __future__ import annotations

from datetime import datetime
import re

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity
from .scene_activity import HueSceneActivityManager


class SceneActivityBaseEntity(HueBaseEntity):
    """Base class for per-group scene activity entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
    ) -> None:
        """Initialize the base scene activity entity for a Hue group.

        Args:
            bridge: The Hue bridge instance.
            manager: Manager tracking active scene state per group.
            group_id: Hue group (room/zone) identifier.
        """
        super().__init__(bridge, bridge.api.groups, bridge.api.groups.get(group_id))
        self._manager = manager
        self._group_id = group_id
        self._group_state = manager.get_group_state(group_id)
        group = self.controller[group_id]
        group_name = group.metadata.name
        # Compact version used in unique_id’s (lowercase, alnum only)
        self._group_compact = re.sub(r"[^0-9a-z]+", "", group_name.lower())
        # Expose the Hue group resource via standard attribute used elsewhere
        self.group = self.controller[self.resource.id]
        # Provide device info so all scene activity sensors attach to the
        # virtual Hue group device (same pattern used for grouped lights & scenes).
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.group.id)},
            name=group_name,
        )

    async def async_added_to_hass(self) -> None:
        """Register listener on the manager when added to hass."""
        await super().async_added_to_hass()

        @callback
        def _update(_: str) -> None:
            self._group_state = self._manager.get_group_state(self._group_id)
            self.async_write_ha_state()

        self.async_on_remove(self._manager.async_add_listener(self._group_id, _update))


# pylint: disable-next=hass-enforce-class-module
class HueActiveSceneSensor(SceneActivityBaseEntity, SensorEntity):
    """Active regular scene for a Hue group."""

    entity_description = SensorEntityDescription(key="active_scene_sensor")

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
    ) -> None:
        """Initialize the active scene sensor."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_active_scene"
        self._attr_name = "Scene"

    @property
    def native_value(self) -> str | None:
        """Return the current active (regular) scene entity ID."""
        return self._group_state.active_scene_entity_id


# pylint: disable-next=hass-enforce-class-module
class HueActiveSceneNameSensor(SceneActivityBaseEntity, SensorEntity):
    """Active regular scene name for a Hue group."""

    entity_description = SensorEntityDescription(key="active_scene_name_sensor")

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
    ) -> None:
        """Initialize the active scene sensor."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_active_scene_name"
        self._attr_name = "Scene name"

    @property
    def native_value(self) -> str | None:
        """Return the current active (regular) scene name, if any."""
        return self._group_state.active_scene_name


# pylint: disable-next=hass-enforce-class-module
class HueActiveSceneLastRecallSensor(SceneActivityBaseEntity, SensorEntity):
    """Timestamp of the last recall of the active scene."""

    entity_description = SensorEntityDescription(
        key="active_scene_last_recall",
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    def __init__(
        self, bridge: HueBridge, manager: HueSceneActivityManager, group_id: str
    ) -> None:
        """Initialize the last recall timestamp sensor."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{self._group_compact}_active_scene_last_recall"
        self._attr_name = "Last scene recall"

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the last scene recall."""
        return self._group_state.active_scene_last_recall


# pylint: disable-next=hass-enforce-class-module
class HueActiveSceneDynamicBinarySensor(SceneActivityBaseEntity, BinarySensorEntity):
    """Binary sensor indicating if the active scene uses a dynamic palette."""

    entity_description = BinarySensorEntityDescription(
        key="active_scene_is_dynamic", device_class=BinarySensorDeviceClass.RUNNING
    )

    def __init__(
        self, bridge: HueBridge, manager: HueSceneActivityManager, group_id: str
    ) -> None:
        """Initialize the dynamic scene flag sensor."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_active_scene_dynamic"
        self._attr_name = "Dynamic scene"

    @property
    def is_on(self) -> bool | None:
        """Return True if the active scene mode is a dynamic palette."""
        if self._group_state.active_scene_mode is None:
            return None
        return self._group_state.active_scene_mode == "dynamic_palette"


# pylint: disable-next=hass-enforce-class-module
class HueActiveSmartSceneSensor(SceneActivityBaseEntity, SensorEntity):
    """Active smart scene for a Hue group."""

    entity_description = SensorEntityDescription(key="active_scene_sensor")

    def __init__(
        self,
        bridge: HueBridge,
        manager: HueSceneActivityManager,
        group_id: str,
    ) -> None:
        """Initialize the active scene sensor."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_active_smart_scene"
        self._attr_name = "Smart scene"

    @property
    def native_value(self) -> str | None:
        """Return the active smart scene entity ID."""
        return self._group_state.active_smart_scene_entity_id


# pylint: disable-next=hass-enforce-class-module
class HueActiveSmartSceneNameSensor(SceneActivityBaseEntity, SensorEntity):
    """Active smart scene name for a Hue group."""

    entity_description = SensorEntityDescription(key="active_smart_scene_sensor")

    def __init__(
        self, bridge: HueBridge, manager: HueSceneActivityManager, group_id: str
    ) -> None:
        """Initialize the active smart scene sensor."""
        super().__init__(bridge, manager, group_id)
        self._attr_unique_id = f"{group_id}_active_smart_scene_name"
        self._attr_name = "Smart scene name"

    @property
    def native_value(self) -> str | None:
        """Return the active smart scene name, if any."""
        return self._group_state.active_smart_scene_name
