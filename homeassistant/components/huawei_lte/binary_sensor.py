"""Support for Huawei LTE binary sensors."""

import logging
from typing import Optional

import attr
from huawei_lte_api.enums.cradle import ConnectionStatusEnum

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDevice,
)
from homeassistant.const import CONF_URL

from . import HuaweiLteBaseEntity
from .const import DOMAIN, KEY_MONITORING_STATUS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up from config entry."""
    router = hass.data[DOMAIN].routers[config_entry.data[CONF_URL]]
    entities = []

    if router.data.get(KEY_MONITORING_STATUS):
        entities.append(HuaweiLteMobileConnectionBinarySensor(router))

    async_add_entities(entities, True)


@attr.s
class HuaweiLteBaseBinarySensor(HuaweiLteBaseEntity, BinarySensorDevice):
    """Huawei LTE binary sensor device base class."""

    key: str
    item: str
    _raw_state: Optional[str] = attr.ib(init=False, default=None)

    async def async_added_to_hass(self):
        """Subscribe to needed data on add."""
        await super().async_added_to_hass()
        self.router.subscriptions[self.key].add(f"{BINARY_SENSOR_DOMAIN}/{self.item}")

    async def async_will_remove_from_hass(self):
        """Unsubscribe from needed data on remove."""
        await super().async_will_remove_from_hass()
        self.router.subscriptions[self.key].remove(
            f"{BINARY_SENSOR_DOMAIN}/{self.item}"
        )

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


CONNECTION_STATE_ATTRIBUTES = {
    str(ConnectionStatusEnum.CONNECTING): "Connecting",
    str(ConnectionStatusEnum.DISCONNECTING): "Disconnecting",
    str(ConnectionStatusEnum.CONNECT_FAILED): "Connect failed",
    str(ConnectionStatusEnum.CONNECT_STATUS_NULL): "Status not available",
    str(ConnectionStatusEnum.CONNECT_STATUS_ERROR): "Status error",
}


@attr.s
class HuaweiLteMobileConnectionBinarySensor(HuaweiLteBaseBinarySensor):
    """Huawei LTE mobile connection binary sensor."""

    def __attrs_post_init__(self):
        """Initialize identifiers."""
        self.key = KEY_MONITORING_STATUS
        self.item = "ConnectionStatus"

    @property
    def _entity_name(self) -> str:
        return "Mobile connection"

    @property
    def _device_unique_id(self) -> str:
        return f"{self.key}.{self.item}"

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on."""
        return self._raw_state and int(self._raw_state) in (
            ConnectionStatusEnum.CONNECTED,
            ConnectionStatusEnum.DISCONNECTING,
        )

    @property
    def assumed_state(self) -> bool:
        """Return True if real state is assumed, not known."""
        return not self._raw_state or int(self._raw_state) not in (
            ConnectionStatusEnum.CONNECT_FAILED,
            ConnectionStatusEnum.CONNECTED,
            ConnectionStatusEnum.DISCONNECTED,
        )

    @property
    def icon(self):
        """Return mobile connectivity sensor icon."""
        return "mdi:signal" if self.is_on else "mdi:signal-off"

    @property
    def device_state_attributes(self):
        """Get additional attributes related to connection status."""
        attributes = super().device_state_attributes
        if self._raw_state in CONNECTION_STATE_ATTRIBUTES:
            if attributes is None:
                attributes = {}
            attributes["additional_state"] = CONNECTION_STATE_ATTRIBUTES[
                self._raw_state
            ]
        return attributes
