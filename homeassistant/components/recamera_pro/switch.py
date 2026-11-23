"""Switch platform for the motion-detect reCamera Pro App."""

from recamera_protocol import RecameraError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SOURCE_AVAILABLE
from .coordinator import RecameraCoordinator
from .entity import RecameraEntity, recamera_service_error

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up stream and motion detection switches."""
    coordinator: RecameraCoordinator = config_entry.runtime_data
    entities: list[SwitchEntity] = [
        RecameraRtspStreamSwitch(coordinator, "sub"),
        RecameraRtspStreamSwitch(coordinator, "main"),
    ]
    motion_added = coordinator.data.motion.installed
    if motion_added:
        entities.append(RecameraMotionDetectionSwitch(coordinator))
    async_add_entities(entities)

    @callback
    def _add_motion_switch() -> None:
        nonlocal motion_added
        if motion_added or not coordinator.data.motion.installed:
            return
        motion_added = True
        async_add_entities([RecameraMotionDetectionSwitch(coordinator)])

    config_entry.async_on_unload(coordinator.async_add_listener(_add_motion_switch))


class RecameraRtspStreamSwitch(RecameraEntity, SwitchEntity):
    """Enable or disable RTSP streaming for the main or sub stream."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RecameraCoordinator, stream_id: str) -> None:
        """Initialize one RTSP stream switch."""
        super().__init__(coordinator)
        self._stream_id = stream_id
        self._attr_translation_key = f"{stream_id}_rtsp_stream"
        self._attr_unique_id = f"{coordinator.device_id}_{stream_id}_rtsp_stream"

    @property
    def available(self) -> bool:
        """Return whether stream metadata is available from the device."""
        return super().available and self.coordinator.has_stream_profile(
            self._stream_id
        )

    @property
    def is_on(self) -> bool:
        """Return whether RTSP streaming is currently enabled."""
        return self.coordinator.is_stream_enabled(self._stream_id)

    @property
    def icon(self) -> str:
        """Show active/inactive stream icon."""
        if not self.is_on:
            return "mdi:video-off"
        return "mdi:video-high-definition" if self._stream_id == "main" else "mdi:video"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose stream identifier."""
        return {"stream_id": self._stream_id}

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable RTSP streaming for this stream."""
        try:
            await self.coordinator.async_set_stream_enabled(self._stream_id, True)
        except RecameraError as err:
            raise recamera_service_error(err) from err

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable RTSP streaming for this stream."""
        try:
            await self.coordinator.async_set_stream_enabled(self._stream_id, False)
        except RecameraError as err:
            raise recamera_service_error(err) from err


class RecameraMotionDetectionSwitch(RecameraEntity, SwitchEntity):
    """Start and stop the device-side motion detection App."""

    _attr_translation_key = "motion_detection"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RecameraCoordinator) -> None:
        """Initialize the motion detection switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_motion_detection"

    @property
    def available(self) -> bool:
        """Return whether AppMgr confirmed the motion App state."""
        motion = self.coordinator.data.motion
        return (
            super().available
            and motion.installed
            and motion.app_health == SOURCE_AVAILABLE
            and not motion.transitioning
        )

    @property
    def is_on(self) -> bool:
        """Return whether the App is running."""
        return self.coordinator.data.motion.running

    @property
    def icon(self) -> str:
        """Distinguish the feature switch from motion event entities."""
        if self.coordinator.data.motion.transitioning:
            return "mdi:timer-sand"
        return "mdi:motion-sensor" if self.is_on else "mdi:motion-sensor-off"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose the App identity and observed lifecycle reason."""
        motion = self.coordinator.data.motion
        return {
            "app_id": "motion-detect",
            "source_status": motion.reason,
            "app_health": motion.app_health,
            "error": motion.error,
            "transitioning": motion.transitioning,
            "target_running": motion.target_running,
            "transition_started_at": (
                motion.transition_started_at.isoformat()
                if motion.transition_started_at
                else None
            ),
            "transition_error": motion.transition_error,
        }

    async def async_turn_on(self, **kwargs: object) -> None:
        """Start motion detection."""
        try:
            await self.coordinator.async_set_motion_detection(True)
        except RecameraError as err:
            raise recamera_service_error(err) from err

    async def async_turn_off(self, **kwargs: object) -> None:
        """Stop motion detection."""
        try:
            await self.coordinator.async_set_motion_detection(False)
        except RecameraError as err:
            raise recamera_service_error(err) from err
