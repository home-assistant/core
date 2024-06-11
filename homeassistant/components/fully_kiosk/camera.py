"""Support for Fully Kiosk Browser camera."""

from __future__ import annotations

from fullykiosk.exceptions import FullyKioskError

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the camera."""
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FullyKioskCamera(coordinator)])


class FullyKioskCamera(FullyKioskEntity, Camera):
    """Fully Kiosk Browser camera entity."""

    entity_description = CameraEntityDescription(key="camera", translation_key="camera")
    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(self, coordinator: FullyKioskDataUpdateCoordinator) -> None:
        """Initialize the camera."""
        FullyKioskEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.data['deviceID']}-camera"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        # TODO: use this after https://github.com/cgarwood/python-fullykiosk/pull/20
        # return await self.coordinator.fully.getCamshot()
        fully = self.coordinator.fully
        url = f"http{'s' if fully._rh.use_ssl else ''}://{fully._rh.host}:{fully._rh.port}"  # noqa: SLF001
        params = [("cmd", "getCamshot"), ("password", fully._password)]  # noqa: SLF001
        req_params = {"url": url, "headers": {}, "params": params}
        if not fully._rh.verify_ssl:  # noqa: SLF001
            req_params["ssl"] = False
        async with fully._rh.session.get(**req_params) as response:  # noqa: SLF001
            if response.status != 200:
                raise FullyKioskError(response.status, await response.text())
            return await response.content.read()

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        await self.coordinator.fully.enableMotionDetection()
        await self.coordinator.async_refresh()

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        await self.coordinator.fully.disableMotionDetection()
        await self.coordinator.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = bool(
            self.coordinator.data["settings"].get("motionDetection")
        )
        self.async_write_ha_state()
