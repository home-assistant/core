"""Support for KNX/IP buttons."""

from __future__ import annotations

from xknx.devices import RawValue as XknxRawValue

from homeassistant import config_entries
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, CONF_PAYLOAD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import KNXModule
from .const import CONF_PAYLOAD_LENGTH, KNX_ADDRESS, KNX_MODULE_KEY
from .entity import KnxYamlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KNX binary sensor platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    config: list[ConfigType] = knx_module.config_yaml[Platform.BUTTON]

    async_add_entities(KNXButton(knx_module, entity_config) for entity_config in config)


class KNXButton(KnxYamlEntity, ButtonEntity):
    """Representation of a KNX button."""

    _device: XknxRawValue

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX button."""
        super().__init__(
            knx_module=knx_module,
            device=XknxRawValue(
                xknx=knx_module.xknx,
                name=config[CONF_NAME],
                payload_length=config[CONF_PAYLOAD_LENGTH],
                group_address=config[KNX_ADDRESS],
            ),
        )
        self._payload = config[CONF_PAYLOAD]
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = (
            f"{self._device.remote_value.group_address}_{self._payload}"
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self._device.set(self._payload)
