"""Code to handle a Livisi shutters."""
from __future__ import annotations

from typing import Any
import uuid

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LIVISI_NAMESPACE_COSIP,
    LIVISI_SHUTTERSTATE_CHANGE,
    LOGGER,
    SHUTTER_DEVICE_TYPE,
)
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def handle_coordinator_update() -> None:
        """Add cover."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[CoverEntity] = []
        for device in shc_devices:
            if (
                device["type"] == SHUTTER_DEVICE_TYPE
                and device["id"] not in coordinator.devices
            ):
                livisi_shutter: CoverEntity = LivisiShutter(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s", device["type"])
                coordinator.devices.add(device["id"])
                entities.append(livisi_shutter)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiShutter(LivisiEntity, CoverEntity):
    """Represents the Livisi Switch."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi switch."""
        super().__init__(config_entry, coordinator, device)
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        self._capability_id = self.capabilities["RollerShutterActuator"]
        self._livisiCoverPosition = 0

    async def send_livisi_shutter_command(self, namespace, commandtype, params) -> dict:
        """Send a generic command to the Livisi API."""
        set_state_payload: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "type": commandtype,
            "namespace": namespace,
            "target": self._capability_id,
            "params": params,
        }
        return await self.aio_livisi.async_send_authorized_request(
            "post", "action", payload=set_state_payload
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shutter."""
        open_cover_params: dict[str, Any] = {
            "rampDirection": {"type": "Constant", "value": "RampUp"}
        }
        response = await self.send_livisi_shutter_command(
            LIVISI_NAMESPACE_COSIP, "StartRamp", open_cover_params
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(
                f"Failed to open shutter {self._attr_device_info['name']}"
            )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shutter."""
        close_cover_params: dict[str, Any] = {
            "rampDirection": {"type": "Constant", "value": "RampDown"}
        }
        response = await self.send_livisi_shutter_command(
            LIVISI_NAMESPACE_COSIP, "StartRamp", close_cover_params
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(
                f"Failed to close shutter {self._attr_device_info['name']}"
            )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the shutter."""
        response = await self.send_livisi_shutter_command(
            LIVISI_NAMESPACE_COSIP, "StopRamp", {}
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(
                f"Failed to close shutter {self._attr_device_info['name']}"
            )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set shutter to specific position."""
        set_position_params: dict[str, Any] = {
            "shutterLevel": {"type": "Constant", "value": kwargs[ATTR_POSITION]}
        }
        response = await self.send_livisi_shutter_command(
            LIVISI_NAMESPACE_COSIP, "SetState", set_position_params
        )
        LOGGER.debug(response)
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(
                f"Failed to set position of shutter {self._attr_device_info['name']}"
            )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._attr_current_cover_position is not None:
            return self._attr_current_cover_position <= 0
        return None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        response = await self.coordinator.async_get_device_state(
            self._capability_id, "shutterLevel"
        )
        if response is None:
            self._attr_current_cover_position = -1
            self._attr_available = False
        else:
            self._attr_current_cover_position = response
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_SHUTTERSTATE_CHANGE}_{self._capability_id}",
                self.update_states,
            )
        )

    @callback
    def update_states(self, shutterLevel: Any) -> None:
        """Update the state of the switch device."""
        self._attr_current_cover_position = shutterLevel
        self.async_write_ha_state()

    @callback
    def fetch_current_state(self, data) -> None:
        """Fetch current state of device."""
