"""Button for the Tile BLE integration."""

from typing import override

from homeassistant.components.bluetooth import (
    BluetoothReachabilityIntent,
    async_address_reachability_diagnostics,
    async_ble_device_from_address,
)
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_AUTH_KEY, DOMAIN
from .coordinator import TileBleConfigEntry, TileBleCoordinator
from .entity import TileBleEntity
from .toa import TileBleDevice, TileBleError

# Ringing needs a Bluetooth connection, so ring one Tile at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TileBleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tile BLE ring button."""
    async_add_entities(
        [TileBleRingButton(entry.runtime_data, entry.title, entry.data[CONF_AUTH_KEY])]
    )


class TileBleRingButton(TileBleEntity, ButtonEntity):
    """Makes a Tile ring."""

    _attr_translation_key = "ring"

    def __init__(
        self, coordinator: TileBleCoordinator, name: str, auth_key: str
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, name)
        self._attr_unique_id = f"{coordinator.address}_ring"
        self._auth_key = auth_key

    @override
    async def async_press(self) -> None:
        """Ring the Tile."""
        address = self.coordinator.address
        if not (
            ble_device := async_ble_device_from_address(
                self.hass, address, connectable=True
            )
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={
                    "reason": async_address_reachability_diagnostics(
                        self.hass, address, BluetoothReachabilityIntent.CONNECTION
                    )
                },
            )
        try:
            await TileBleDevice(ble_device, self._auth_key).async_ring()
        except TileBleError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ring_failed",
                translation_placeholders={"error": str(err)},
            ) from err
