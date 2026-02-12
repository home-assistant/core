"""Support for KNX fan entities."""

from __future__ import annotations

import logging
import math
from typing import Any

from propcache.api import cached_property
from xknx.devices import Fan as XknxFan
from xknx.telegram.address import parse_device_group_address

from homeassistant import config_entries
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .const import CONF_SYNC_STATE, DOMAIN, KNX_ADDRESS, KNX_MODULE_KEY, FanConf
from .entity import KnxUiEntity, KnxUiEntityPlatformController, KnxYamlEntity
from .knx_module import KNXModule
from .schema import FanSchema
from .storage.const import (
    CONF_ENTITY,
    CONF_GA_OSCILLATION,
    CONF_GA_SPEED,
    CONF_GA_STEP,
    CONF_GA_SWITCH,
    CONF_SPEED,
)
from .storage.util import ConfigExtractor

_LOGGER = logging.getLogger(__name__)


@callback
def async_migrate_yaml_uids(
    hass: HomeAssistant, platform_config: list[ConfigType]
) -> None:
    """Migrate entities unique_id for YAML switch-only fan entities."""
    # issue was introduced in 2026.1 - this migration in 2026.2
    ent_reg = er.async_get(hass)
    invalid_uid = str(None)
    if (
        none_entity_id := ent_reg.async_get_entity_id(Platform.FAN, DOMAIN, invalid_uid)
    ) is None:
        return
    for config in platform_config:
        if not config.get(KNX_ADDRESS) and (
            new_uid_base := config.get(FanSchema.CONF_SWITCH_ADDRESS)
        ):
            break
    else:
        _LOGGER.info(
            "No YAML entry found to migrate fan entity '%s' unique_id from '%s'. Removing entry",
            none_entity_id,
            invalid_uid,
        )
        ent_reg.async_remove(none_entity_id)
        return
    new_uid = str(
        parse_device_group_address(
            new_uid_base[0],  # list of group addresses - first item is sending address
        )
    )
    try:
        ent_reg.async_update_entity(none_entity_id, new_unique_id=str(new_uid))
        _LOGGER.info(
            "Migrating fan entity '%s' unique_id from '%s' to %s",
            none_entity_id,
            invalid_uid,
            new_uid,
        )
    except ValueError:
        # New unique_id already exists - remove invalid entry. User might have changed YAML
        _LOGGER.info(
            "Failed to migrate fan entity '%s' unique_id from '%s' to '%s'. "
            "Removing the invalid entry",
            none_entity_id,
            invalid_uid,
            new_uid,
        )
        ent_reg.async_remove(none_entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up fan(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.FAN,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiFan,
        ),
    )

    entities: list[_KnxFan] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.FAN):
        async_migrate_yaml_uids(hass, yaml_platform_config)
        entities.extend(
            KnxYamlFan(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.FAN):
        entities.extend(
            KnxUiFan(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxFan(FanEntity):
    """Representation of a KNX fan."""

    _device: XknxFan
    _step_range: tuple[int, int] | None

    def _get_knx_speed(self, percentage: int) -> int:
        """Convert percentage to KNX speed value."""
        if self._step_range is not None:
            return math.ceil(percentage_to_ranged_value(self._step_range, percentage))
        return percentage

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self._device.set_speed(self._get_knx_speed(percentage))

    @cached_property
    def supported_features(self) -> FanEntityFeature:
        """Flag supported features."""
        flags = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if self._device.speed.initialized:
            flags |= FanEntityFeature.SET_SPEED
        if self._device.supports_oscillation:
            flags |= FanEntityFeature.OSCILLATE
        return flags

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        if self._device.current_speed is None:
            return None

        if self._step_range:
            return ranged_value_to_percentage(
                self._step_range, self._device.current_speed
            )
        return self._device.current_speed

    @cached_property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if self._step_range is None:
            return super().speed_count
        return int_states_in_range(self._step_range)

    @property
    def is_on(self) -> bool:
        """Return the current fan state of the device."""
        return self._device.is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        speed = self._get_knx_speed(percentage) if percentage is not None else None
        await self._device.turn_on(speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._device.turn_off()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self._device.set_oscillation(oscillating)

    @property
    def oscillating(self) -> bool | None:
        """Return whether or not the fan is currently oscillating."""
        return self._device.current_oscillation


class KnxYamlFan(_KnxFan, KnxYamlEntity):
    """Representation of a KNX fan configured from YAML."""

    _device: XknxFan

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize of KNX fan."""
        max_step = config.get(FanConf.MAX_STEP)
        super().__init__(
            knx_module=knx_module,
            device=XknxFan(
                xknx=knx_module.xknx,
                name=config[CONF_NAME],
                group_address_speed=config.get(KNX_ADDRESS),
                group_address_speed_state=config.get(FanSchema.CONF_STATE_ADDRESS),
                group_address_oscillation=config.get(
                    FanSchema.CONF_OSCILLATION_ADDRESS
                ),
                group_address_oscillation_state=config.get(
                    FanSchema.CONF_OSCILLATION_STATE_ADDRESS
                ),
                group_address_switch=config.get(FanSchema.CONF_SWITCH_ADDRESS),
                group_address_switch_state=config.get(
                    FanSchema.CONF_SWITCH_STATE_ADDRESS
                ),
                max_step=max_step,
                sync_state=config.get(CONF_SYNC_STATE, True),
            ),
        )
        # FanSpeedMode.STEP if max_step is set
        self._step_range: tuple[int, int] | None = (1, max_step) if max_step else None
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)

        if self._device.speed.group_address:
            self._attr_unique_id = str(self._device.speed.group_address)
        else:
            self._attr_unique_id = str(self._device.switch.group_address)


class KnxUiFan(_KnxFan, KnxUiEntity):
    """Representation of a KNX fan configured from UI."""

    _device: XknxFan

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize of KNX fan."""
        knx_conf = ConfigExtractor(config[DOMAIN])
        # max_step is required for step mode, thus can be used to differentiate modes
        max_step: int | None = knx_conf.get(CONF_SPEED, FanConf.MAX_STEP)
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        if max_step:
            # step control
            speed_write = knx_conf.get_write(CONF_SPEED, CONF_GA_STEP)
            speed_state = knx_conf.get_state_and_passive(CONF_SPEED, CONF_GA_STEP)
        else:
            # percentage control
            speed_write = knx_conf.get_write(CONF_SPEED, CONF_GA_SPEED)
            speed_state = knx_conf.get_state_and_passive(CONF_SPEED, CONF_GA_SPEED)

        self._device = XknxFan(
            xknx=knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            group_address_speed=speed_write,
            group_address_speed_state=speed_state,
            group_address_oscillation=knx_conf.get_write(CONF_GA_OSCILLATION),
            group_address_oscillation_state=knx_conf.get_state_and_passive(
                CONF_GA_OSCILLATION
            ),
            group_address_switch=knx_conf.get_write(CONF_GA_SWITCH),
            group_address_switch_state=knx_conf.get_state_and_passive(CONF_GA_SWITCH),
            max_step=max_step,
            sync_state=knx_conf.get(CONF_SYNC_STATE),
        )
        # FanSpeedMode.STEP if max_step is set
        self._step_range: tuple[int, int] | None = (1, max_step) if max_step else None
