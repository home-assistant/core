"""Support for KNX/IP select entities."""
from __future__ import annotations

from xknx import XKNX
from xknx.devices import Device as XknxDevice, RawValue

from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    DOMAIN,
    KNX_ADDRESS,
)
from .knx_entity import KnxEntity
from .schema import SelectSchema


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up select entities for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return
    platform_config = discovery_info["platform_config"]
    xknx: XKNX = hass.data[DOMAIN].xknx

    async_add_entities(
        KNXSelect(xknx, entity_config) for entity_config in platform_config
    )


def _create_raw_value(xknx: XKNX, config: ConfigType) -> RawValue:
    """Return a KNX RawValue to be used within XKNX."""
    return RawValue(
        xknx,
        name=config[CONF_NAME],
        payload_length=config[SelectSchema.CONF_PAYLOAD_LENGTH],
        group_address=config[KNX_ADDRESS],
        group_address_state=config.get(CONF_STATE_ADDRESS),
        respond_to_read=config[CONF_RESPOND_TO_READ],
        sync_state=config[CONF_SYNC_STATE],
    )


class KNXSelect(KnxEntity, SelectEntity, RestoreEntity):
    """Representation of a KNX select."""

    _device: RawValue

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize a KNX select."""
        super().__init__(_create_raw_value(xknx, config))
        self._option_payloads: dict[str, int] = {
            option[SelectSchema.CONF_OPTION]: option[SelectSchema.CONF_PAYLOAD]
            for option in config[SelectSchema.CONF_OPTIONS]
        }
        self._attr_options = list(self._option_payloads)
        self._attr_current_option = None
        self._attr_unique_id = str(self._device.remote_value.group_address)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if not self._device.remote_value.readable and (
            last_state := await self.async_get_last_state()
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                await self._device.remote_value.update_value(
                    self._option_payloads.get(last_state.state)
                )

    async def after_update_callback(self, device: XknxDevice) -> None:
        """Call after device was updated."""
        self._attr_current_option = self.option_from_payload(
            self._device.remote_value.value
        )
        await super().after_update_callback(device)

    def option_from_payload(self, payload: int | None) -> str | None:
        """Return the option a given payload is assigned to."""
        try:
            return next(
                key for key, value in self._option_payloads.items() if value == payload
            )
        except StopIteration:
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        payload = self._option_payloads[option]
        await self._device.set(payload)
