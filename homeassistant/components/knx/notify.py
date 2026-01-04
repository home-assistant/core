"""Support for KNX notify entities."""

from __future__ import annotations

from xknx import XKNX
from xknx.devices import Notification as XknxNotification

from homeassistant import config_entries
from homeassistant.components.notify import NotifyEntity
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import KNX_ADDRESS, KNX_MODULE_KEY
from .entity import KnxYamlEntity
from .knx_module import KNXModule


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up notify(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    config: list[ConfigType] = knx_module.config_yaml[Platform.NOTIFY]

    async_add_entities(KNXNotify(knx_module, entity_config) for entity_config in config)


def _create_notification_instance(xknx: XKNX, config: ConfigType) -> XknxNotification:
    """Return a KNX Notification to be used within XKNX."""
    return XknxNotification(
        xknx,
        name=config.get(CONF_NAME, ""),
        group_address=config[KNX_ADDRESS],
        value_type=config[CONF_TYPE],
    )


class KNXNotify(KnxYamlEntity, NotifyEntity):
    """Representation of a KNX notification entity."""

    _device: XknxNotification

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX notification."""
        self._device = _create_notification_instance(knx_module.xknx, config)
        super().__init__(
            knx_module=knx_module,
            unique_id=str(self._device.remote_value.group_address),
            name=config.get(CONF_NAME),
            entity_category=config.get(CONF_ENTITY_CATEGORY),
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a notification to knx bus."""
        await self._device.set(message)
