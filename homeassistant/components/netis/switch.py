"""switch platform for Netis Router.

Provides on/off toggle switches for:

  - **WiFi 2.4G**: enables/disables the 2.4 GHz radio (``wificfg.2G.Enable``)
  - **WiFi 5G**: enables/disables the 5 GHz radio (``wificfg.5G.Enable``)
  - **Indicator LED**: turns the front-panel LEDs on/off
    (``system.@system[0].ledoff``, inverted: ledoff=0 means ON)

Write operations use ``uci.set`` + ``uci.apply`` with a hard timeout
(``WRITE_TIMEOUT``) to prevent HA from hanging when the firmware's rpcd
serialises config writes. The optimistic state update ensures the UI
responds immediately; the next poll confirms the actual state.
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BAND_2G, BAND_5G
from .coordinator import NetisCoordinator
from .entity import NetisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Netis switches (WiFi + LED indicator)."""
    coordinator: NetisCoordinator = entry.runtime_data
    async_add_entities(
        [
            NetisWifiSwitch(coordinator, BAND_2G, "WiFi 2.4G"),
            NetisWifiSwitch(coordinator, BAND_5G, "WiFi 5G"),
            NetisLedSwitch(coordinator),
        ]
    )


class NetisWifiSwitch(NetisEntity, SwitchEntity):
    """Toggle a WiFi band on or off."""

    _attr_icon = "mdi:wifi"

    def __init__(
        self, coordinator: NetisCoordinator, band: str, name: str
    ) -> None:
        super().__init__(coordinator)
        self._band = band
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-wifi-{band}"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.wifi_enabled.get(self._band)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the WiFi band."""
        await self.coordinator.client.set_wifi_config(
            self._band, {"Enable": "1"}
        )
        # Optimistic update; next poll confirms.
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the WiFi band.

        Disabling will drop all wireless clients on this band for ~10-20s
        while the radio reconfigures.
        """
        await self.coordinator.client.set_wifi_config(
            self._band, {"Enable": "0"}
        )
        self.async_write_ha_state()


class NetisLedSwitch(NetisEntity, SwitchEntity):
    """Toggle the front-panel indicator LEDs."""

    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator: NetisCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Indicator LED"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-led"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.led_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the indicator LEDs on."""
        await self.coordinator.client.set_led(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the indicator LEDs off (sleep mode)."""
        await self.coordinator.client.set_led(False)
        self.async_write_ha_state()
