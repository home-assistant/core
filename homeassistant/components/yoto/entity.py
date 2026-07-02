"""Base entity for the Yoto integration."""

from typing import Any, override

from yoto_api import YotoError, YotoPlayer

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import YotoDataUpdateCoordinator


class YotoEntity(CoordinatorEntity[YotoDataUpdateCoordinator]):
    """Base class for Yoto entities tied to a single player."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._player_id = player.id
        device = player.device
        mac = player.info.mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player.id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            manufacturer=MANUFACTURER,
            model=player.model,
            model_id=device.device_type,
            hw_version=device.generation,
            name=player.name,
            sw_version=player.info.firmware_version,
        )

    @property
    def player(self) -> YotoPlayer:
        """Return the live player record from the client."""
        return self.coordinator.data[self._player_id]

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._player_id in self.coordinator.data


class YotoPlayerEntity(YotoEntity):
    """Base class for entities reflecting live player state over MQTT."""

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and bool(self.player.is_online)


class YotoConfigEntity(YotoEntity):
    """Base class for entities that write player settings over REST."""

    async def _async_set_config(self, **fields: Any) -> None:
        """Write player config fields and refresh the local copy."""
        client = self.coordinator.client
        try:
            await client.set_player_config(self._player_id, **fields)
            await client.update_player_info(self._player_id)
        except YotoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="config_update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.coordinator.async_set_updated_data(client.players)
