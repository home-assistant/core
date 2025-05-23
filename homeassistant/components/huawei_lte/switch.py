"""Support for Huawei LTE switches."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchDeviceClass,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    KEY_DIALUP_MOBILE_DATASWITCH,
    KEY_WLAN_WIFI_GUEST_NETWORK_SWITCH,
)
from .entity import HuaweiLteBaseEntityWithDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up from config entry."""
    router = hass.data[DOMAIN].routers[config_entry.entry_id]
    switches: list[Entity] = []

    if router.data.get(KEY_DIALUP_MOBILE_DATASWITCH):
        switches.append(HuaweiLteMobileDataSwitch(router))

    if router.data.get(KEY_WLAN_WIFI_GUEST_NETWORK_SWITCH, {}).get("WifiEnable"):
        switches.append(HuaweiLteWifiGuestNetworkSwitch(router))

    async_add_entities(switches, True)


class HuaweiLteBaseSwitch(HuaweiLteBaseEntityWithDevice, SwitchEntity):
    """Huawei LTE switch device base class."""

    key: str
    item: str

    _attr_device_class: SwitchDeviceClass = SwitchDeviceClass.SWITCH
    _raw_state: str | None = None

    def _turn(self, state: bool) -> None:
        raise NotImplementedError

    def turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        self._turn(state=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        self._turn(state=False)

    async def async_added_to_hass(self) -> None:
        """Subscribe to needed data on add."""
        await super().async_added_to_hass()
        self.router.subscriptions[self.key].append(f"{SWITCH_DOMAIN}/{self.item}")

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from needed data on remove."""
        await super().async_will_remove_from_hass()
        self.router.subscriptions[self.key].remove(f"{SWITCH_DOMAIN}/{self.item}")

    async def async_update(self) -> None:
        """Update state."""
        try:
            value = self.router.data[self.key][self.item]
        except KeyError:
            _LOGGER.debug("%s[%s] not in data", self.key, self.item)
            self._available = False
            return
        self._available = True
        self._raw_state = str(value)


class HuaweiLteMobileDataSwitch(HuaweiLteBaseSwitch):
    """Huawei LTE mobile data switch device."""

    _attr_translation_key: str = "mobile_data"

    key = KEY_DIALUP_MOBILE_DATASWITCH
    item = "dataswitch"

    @property
    def _device_unique_id(self) -> str:
        return f"{self.key}.{self.item}"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on."""
        return self._raw_state == "1"

    def _turn(self, state: bool) -> None:
        value = 1 if state else 0
        self.router.client.dial_up.set_mobile_dataswitch(dataswitch=value)
        self._raw_state = str(value)
        self.schedule_update_ha_state()


class HuaweiLteWifiGuestNetworkSwitch(HuaweiLteBaseSwitch):
    """Huawei LTE WiFi guest network switch device."""

    _attr_translation_key: str = "wifi_guest_network"

    key = KEY_WLAN_WIFI_GUEST_NETWORK_SWITCH
    item = "WifiEnable"

    @property
    def _device_unique_id(self) -> str:
        return f"{self.key}.{self.item}"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on."""
        return self._raw_state == "1"

    def _turn(self, state: bool) -> None:
        self.router.client.wlan.wifi_guest_network_switch(state)
        self._raw_state = "1" if state else "0"
        self.schedule_update_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        return {"ssid": self.router.data[self.key].get("WifiSsid")}
