"""Support for KNX/IP switches."""

from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Switch as XknxSwitch

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import KNXModule
from .const import CONF_RESPOND_TO_READ, DATA_KNX_CONFIG, DOMAIN, KNX_ADDRESS
from .knx_entity import KnxEntity
from .schema import SwitchSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch(es) for KNX platform."""
    knx_module: KNXModule = hass.data[DOMAIN]

    yaml_config: list[ConfigType] | None
    if yaml_config := hass.data[DATA_KNX_CONFIG].get(Platform.SWITCH):
        async_add_entities(
            KnxYamlSwitch(knx_module.xknx, entity_config)
            for entity_config in yaml_config
        )
    ui_config: dict[str, ConfigType] | None
    if ui_config := knx_module.config_store.data["entities"].get(Platform.SWITCH):
        async_add_entities(
            KnxUiSwitch(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )

    @callback
    def add_new_ui_switch(unique_id: str, config: dict[str, Any]) -> None:
        """Add KNX entity at runtime."""
        async_add_entities([KnxUiSwitch(knx_module, unique_id, config)])

    knx_module.config_store.async_add_entity[Platform.SWITCH] = add_new_ui_switch


class _KnxSwitch(KnxEntity, SwitchEntity, RestoreEntity):
    """Base class for a KNX switch."""

    _device: XknxSwitch

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if not self._device.switch.readable and (
            last_state := await self.async_get_last_state()
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._device.switch.value = last_state.state == STATE_ON

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self._device.state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._device.set_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._device.set_off()


class KnxYamlSwitch(_KnxSwitch):
    """Representation of a KNX switch configured from YAML."""

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of KNX switch."""
        super().__init__(
            device=XknxSwitch(
                xknx,
                name=config[CONF_NAME],
                group_address=config[KNX_ADDRESS],
                group_address_state=config.get(SwitchSchema.CONF_STATE_ADDRESS),
                respond_to_read=config[CONF_RESPOND_TO_READ],
                invert=config[SwitchSchema.CONF_INVERT],
            )
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_unique_id = str(self._device.switch.group_address)


class KnxUiSwitch(_KnxSwitch):
    """Representation of a KNX switch configured from UI."""

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize of KNX switch."""
        super().__init__(
            device=XknxSwitch(
                knx_module.xknx,
                name=config["entity"][CONF_NAME],
                group_address=config["knx"]["ga_switch"]["write"],
                group_address_state=[
                    config["knx"]["ga_switch"]["state"],
                    *config["knx"]["ga_switch"]["passive"],
                ],
                respond_to_read=config["knx"][CONF_RESPOND_TO_READ],
                invert=config["knx"]["invert"],
            )
        )
        self._attr_entity_category = config["entity"][CONF_ENTITY_CATEGORY]
        self._attr_unique_id = unique_id
        if device_info := config["entity"].get("device_info"):
            self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_info)})
            self._attr_has_entity_name = True

        knx_module.config_store.entities[unique_id] = self
