"""Support for KNX/IP binary sensors."""

from __future__ import annotations

from typing import Any

from xknx.devices import BinarySensor as XknxBinarySensor

from homeassistant import config_entries
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import KNXModule
from .const import (
    ATTR_COUNTER,
    ATTR_SOURCE,
    CONF_CONTEXT_TIMEOUT,
    CONF_IGNORE_INTERNAL_STATE,
    CONF_INVERT,
    CONF_RESET_AFTER,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    DOMAIN,
    KNX_MODULE_KEY,
)
from .entity import KnxUiEntity, KnxUiEntityPlatformController, KnxYamlEntity
from .storage.const import CONF_ENTITY, CONF_GA_PASSIVE, CONF_GA_SENSOR, CONF_GA_STATE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KNX binary sensor platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.BINARY_SENSOR,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiBinarySensor,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.BINARY_SENSOR):
        entities.extend(
            KnxYamlBinarySensor(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(
        Platform.BINARY_SENSOR
    ):
        entities.extend(
            KnxUiBinarySensor(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxBinarySensor(BinarySensorEntity, RestoreEntity):
    """Representation of a KNX binary sensor."""

    _device: XknxBinarySensor

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._device.remote_value.update_value(last_state.state == STATE_ON)

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._device.is_on()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific state attributes."""
        attr: dict[str, Any] = {}

        if self._device.counter is not None:
            attr[ATTR_COUNTER] = self._device.counter
        if self._device.last_telegram is not None:
            attr[ATTR_SOURCE] = str(self._device.last_telegram.source_address)
        return attr


class KnxYamlBinarySensor(_KnxBinarySensor, KnxYamlEntity):
    """Representation of a KNX binary sensor configured from YAML."""

    _device: XknxBinarySensor

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize of KNX binary sensor."""
        super().__init__(
            knx_module=knx_module,
            device=XknxBinarySensor(
                xknx=knx_module.xknx,
                name=config[CONF_NAME],
                group_address_state=config[CONF_STATE_ADDRESS],
                invert=config[CONF_INVERT],
                sync_state=config[CONF_SYNC_STATE],
                ignore_internal_state=config[CONF_IGNORE_INTERNAL_STATE],
                context_timeout=config.get(CONF_CONTEXT_TIMEOUT),
                reset_after=config.get(CONF_RESET_AFTER),
            ),
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_force_update = self._device.ignore_internal_state
        self._attr_unique_id = str(self._device.remote_value.group_address_state)


class KnxUiBinarySensor(_KnxBinarySensor, KnxUiEntity):
    """Representation of a KNX binary sensor configured from UI."""

    _device: XknxBinarySensor

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize KNX binary sensor."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        self._device = XknxBinarySensor(
            xknx=knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            group_address_state=[
                config[DOMAIN][CONF_GA_SENSOR][CONF_GA_STATE],
                *config[DOMAIN][CONF_GA_SENSOR][CONF_GA_PASSIVE],
            ],
            sync_state=config[DOMAIN][CONF_SYNC_STATE],
            invert=config[DOMAIN].get(CONF_INVERT, False),
            ignore_internal_state=config[DOMAIN].get(CONF_IGNORE_INTERNAL_STATE, False),
            context_timeout=config[DOMAIN].get(CONF_CONTEXT_TIMEOUT),
            reset_after=config[DOMAIN].get(CONF_RESET_AFTER),
        )
        self._attr_force_update = self._device.ignore_internal_state
