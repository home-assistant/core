"""Support for Huawei LTE switches."""

import logging
from typing import Optional

import attr

from homeassistant.components.switch import (
    DEVICE_CLASS_SWITCH,
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
)
from homeassistant.const import CONF_URL

from . import HuaweiLteBaseEntity
from .const import DOMAIN, KEY_DIALUP_MOBILE_DATASWITCH

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up from config entry."""
    router = hass.data[DOMAIN].routers[config_entry.data[CONF_URL]]
    switches = []

    if router.data.get(KEY_DIALUP_MOBILE_DATASWITCH):
        switches.append(HuaweiLteMobileDataSwitch(router))

    async_add_entities(switches, True)


@attr.s
class HuaweiLteBaseSwitch(HuaweiLteBaseEntity, SwitchEntity):
    """Huawei LTE switch device base class."""

    key: str
    item: str
    _raw_state: Optional[str] = attr.ib(init=False, default=None)

    def _turn(self, state: bool) -> None:
        raise NotImplementedError

    def turn_on(self, **kwargs):
        """Turn switch on."""
        self._turn(state=True)

    def turn_off(self, **kwargs):
        """Turn switch off."""
        self._turn(state=False)

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_SWITCH

    async def async_added_to_hass(self):
        """Subscribe to needed data on add."""
        await super().async_added_to_hass()
        self.router.subscriptions[self.key].add(f"{SWITCH_DOMAIN}/{self.item}")

    async def async_will_remove_from_hass(self):
        """Unsubscribe from needed data on remove."""
        await super().async_will_remove_from_hass()
        self.router.subscriptions[self.key].remove(f"{SWITCH_DOMAIN}/{self.item}")

    async def async_update(self):
        """Update state."""
        try:
            value = self.router.data[self.key][self.item]
        except KeyError:
            _LOGGER.debug("%s[%s] not in data", self.key, self.item)
            self._available = False
            return
        self._available = True
        self._raw_state = str(value)


@attr.s
class HuaweiLteMobileDataSwitch(HuaweiLteBaseSwitch):
    """Huawei LTE mobile data switch device."""

    def __attrs_post_init__(self):
        """Initialize identifiers."""
        self.key = KEY_DIALUP_MOBILE_DATASWITCH
        self.item = "dataswitch"

    @property
    def _entity_name(self) -> str:
        return "Mobile data"

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

    @property
    def icon(self):
        """Return switch icon."""
        return "mdi:signal" if self.is_on else "mdi:signal-off"
