"""Base entity for the system bridge integration."""

from typing import override

from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.display_control import DisplayControl
from systembridgeconnector.models.modules.displays import Display, DisplayPowerState

from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator


class SystemBridgeEntity(CoordinatorEntity[SystemBridgeDataUpdateCoordinator]):
    """Defines a base System Bridge entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        key: str | None = None,
    ) -> None:
        """Initialize the System Bridge entity."""
        super().__init__(coordinator)

        system = coordinator.data.system
        assert system is not None

        self._hostname = system.hostname
        self._attr_unique_id = (
            f"{system.uuid}_{key}" if key is not None else system.uuid
        )
        self._configuration_url = f"http://{self._hostname}:{api_port}/settings"
        self._mac_address = system.mac_address
        self._uuid = system.uuid
        self._version = system.version

        self._attr_device_info = DeviceInfo(
            configuration_url=self._configuration_url,
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_address)},
            identifiers={(DOMAIN, self._uuid)},
            name=self._hostname,
            sw_version=self._version,
        )


class SystemBridgeDisplayEntity(SystemBridgeEntity):
    """Defines a System Bridge entity that controls a display."""

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        key: str,
        display_id: str,
    ) -> None:
        """Initialize the System Bridge display entity."""
        super().__init__(coordinator, api_port, f"display_{display_id}_{key}")
        self._display_id = display_id
        self._attr_translation_placeholders = {"display_id": display_id}

    @property
    def _display(self) -> Display | None:
        """Return the display, if it is still connected."""
        return next(
            (
                display
                for display in self.coordinator.data.displays
                if display.id == self._display_id
            ),
            None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the display is connected."""
        return super().available and self._display is not None

    async def _async_display_control(
        self,
        brightness: float | None = None,
        power_state: DisplayPowerState | None = None,
    ) -> None:
        """Set the display's brightness or power state."""
        try:
            response = await self.coordinator.websocket_client.display_control(
                DisplayControl(
                    id=self._display_id,
                    brightness=brightness,
                    power_state=power_state,
                )
            )
        except ConnectionClosedException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
                translation_placeholders={
                    "title": self.coordinator.config_entry.title,
                    "host": self.coordinator.config_entry.data[CONF_HOST],
                },
            ) from e
        if response.type == EventType.ERROR:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="display_control_failed",
                translation_placeholders={
                    "display_id": self._display_id,
                    "error": response.message or "",
                },
            )
