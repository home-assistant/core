"""Support for Shelly cameras."""

from dataclasses import dataclass
from typing import Final, override
from urllib.parse import quote

from homeassistant.components.camera import (
    Camera,
    CameraEntityDescription,
    CameraEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
)
from .utils import get_host

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RpcCameraEntityDescription(RpcEntityDescription, CameraEntityDescription):
    """Class to describe a Shelly RPC camera entity."""

    stream: int


RPC_CAMERA_ENTITIES: Final = {
    "stream_0": RpcCameraEntityDescription(
        key="camera",
        stream=0,
        translation_key="stream",
        translation_placeholders={"stream_id": "0"},
        removal_condition=lambda config, _, key: not config[key]["rtsp"]["enable"],
    ),
    "stream_1": RpcCameraEntityDescription(
        key="camera",
        stream=1,
        translation_key="stream",
        translation_placeholders={"stream_id": "1"},
        entity_registry_enabled_default=False,
        removal_condition=lambda config, _, key: not config[key]["rtsp"]["enable"],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Shelly camera entities."""
    if not config_entry.runtime_data.rpc:
        return

    async_setup_entry_rpc(
        hass,
        config_entry,
        async_add_entities,
        RPC_CAMERA_ENTITIES,
        ShellyCameraEntity,
    )


class ShellyCameraEntity(ShellyRpcAttributeEntity, Camera):
    """Shelly camera entity for RPC devices."""

    _attr_brand = "Shelly"
    _attr_supported_features = CameraEntityFeature.STREAM
    entity_description: RpcCameraEntityDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcCameraEntityDescription,
    ) -> None:
        """Initialize Shelly camera entity."""
        super().__init__(coordinator, key, attribute, description)
        Camera.__init__(self)

        self._attr_model = self.coordinator.model

    @override
    @property
    def available(self) -> bool:
        """Available."""
        available = super().available
        if not available:
            return False

        return not self.status["privacy"]

    @override
    @property
    def is_on(self) -> bool:
        """Return True if the camera is running."""
        return (
            self.coordinator.device.initialized and self.status["streamer"] == "running"
        )

    @override
    @property
    def is_recording(self) -> bool:
        """Return True if the camera is currently recording."""
        return bool(self.status.get("recordings"))

    @override
    @property
    def is_streaming(self) -> bool:
        """Return True if the camera is currently streaming."""
        return bool(self.status["streams"] > 0)

    @override
    async def stream_source(self) -> str | None:
        """Return the RTSP stream source for go2rtc."""
        username = self.coordinator.config_entry.data.get(CONF_USERNAME)
        password = self.coordinator.config_entry.data.get(CONF_PASSWORD)
        host = get_host(self.coordinator.config_entry.data[CONF_HOST])

        if username and password:
            return (
                f"rtsp://{quote(username, safe='')}:{quote(password, safe='')}@{host}"
                f"/stream/{self.entity_description.stream}"
            )

        return f"rtsp://{host}/stream/{self.entity_description.stream}"

    @override
    @property
    def use_stream_for_stills(self) -> bool:
        """Use the RTSP stream to generate still images."""
        return True
