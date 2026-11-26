"""Button for the Tile BLE integration."""

from typing import override

from tile_ble import TileBleConnectionError, TileBleDevice, TileBleError

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_AUTH_KEY, DOMAIN
from .coordinator import TileBleConfigEntry, TileBleCoordinator
from .entity import TileBleEntity

# A Tile accepts one connection at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TileBleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tile BLE button."""
    async_add_entities([TileBleRingButton(entry.runtime_data, entry.title)])


class TileBleRingButton(TileBleEntity, ButtonEntity):
    """Makes a Tile ring."""

    _attr_translation_key = "ring"

    def __init__(self, coordinator: TileBleCoordinator, name: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, name)
        self._attr_unique_id = f"{coordinator.address}_ring"

    @override
    async def async_press(self) -> None:
        """Ring the Tile."""
        if not (
            ble_device := async_ble_device_from_address(
                self.hass, self.coordinator.address, connectable=True
            )
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_connectable"
            )
        device = TileBleDevice(
            ble_device, self.coordinator.config_entry.data[CONF_AUTH_KEY]
        )
        try:
            await device.async_ring()
        except TileBleConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except TileBleError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="ring_failed"
            ) from err
