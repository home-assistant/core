"""Support for KNX/IP buttons."""
from __future__ import annotations

from xknx import XKNX
from xknx.devices import RawValue as XknxRawValue

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_PAYLOAD, CONF_PAYLOAD_LENGTH, DOMAIN, KNX_ADDRESS
from .knx_entity import KnxEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up buttons for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return
    platform_config = discovery_info["platform_config"]
    xknx: XKNX = hass.data[DOMAIN].xknx

    async_add_entities(
        KNXButton(xknx, entity_config) for entity_config in platform_config
    )


class KNXButton(KnxEntity, ButtonEntity):
    """Representation of a KNX button."""

    _device: XknxRawValue

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize a KNX button."""
        super().__init__(
            device=XknxRawValue(
                xknx,
                name=config[CONF_NAME],
                payload_length=config[CONF_PAYLOAD_LENGTH],
                group_address=config[KNX_ADDRESS],
            )
        )
        self._payload = config[CONF_PAYLOAD]
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = (
            f"{self._device.remote_value.group_address}_{self._payload}"
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self._device.set(self._payload)
