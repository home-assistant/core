"""select platform for Netis Router.

Provides transmit power selectors for each WiFi band:

  - **2.4G transmit power**: low (2) / middle (50) / high (100)
  - **5G transmit power**: low (2) / middle (50) / high (100)

The firmware only supports three discrete power levels (verified from the
router's ``signal_conditioning.html`` page), so a ``select`` entity is used
rather than a ``number`` slider to prevent sending invalid values.

Write operations use ``uci.set`` + ``uci.apply`` via ``set_wifi_config``.
"""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BAND_2G, BAND_5G, TXPOWER_LEVELS
from .coordinator import NetisCoordinator
from .entity import NetisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Netis TxPower selects."""
    coordinator: NetisCoordinator = entry.runtime_data
    async_add_entities(
        [
            NetisTxPowerSelect(coordinator, BAND_2G, "2.4G transmit power"),
            NetisTxPowerSelect(coordinator, BAND_5G, "5G transmit power"),
        ]
    )


class NetisTxPowerSelect(NetisEntity, SelectEntity):
    """Adjust the transmit power of a WiFi band.

    The firmware exposes three discrete levels (verified via
    signal_conditioning.html): 2 (low), 50 (middle), 100 (high). Sending
    other values is rejected by the router, so a select entity is used
    rather than a number slider.
    """

    _attr_icon = "mdi:signal-variant"
    _attr_options = list(TXPOWER_LEVELS)
    _attr_assumed_state = False

    def __init__(
        self, coordinator: NetisCoordinator, band: str, name: str
    ) -> None:
        super().__init__(coordinator)
        self._band = band
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-txpower-{band}"

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.wifi_txpower.get(self._band)
        if value is None:
            return None
        # Normalise: the router returns strings like "100"; if the value
        # isn't one of the known levels fall back to None (unknown).
        return value if value in TXPOWER_LEVELS else None

    async def async_select_option(self, option: str) -> None:
        """Set the transmit power level."""
        if option not in TXPOWER_LEVELS:
            raise ValueError(
                f"Transmit power {option!r} not in supported levels {TXPOWER_LEVELS}"
            )
        await self.coordinator.client.set_wifi_config(
            self._band, {"TxPower": option}
        )
        self.async_write_ha_state()
