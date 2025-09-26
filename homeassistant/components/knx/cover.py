"""Support for KNX cover entities."""

from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Cover as XknxCover

from homeassistant import config_entries
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SYNC_STATE, DOMAIN, KNX_MODULE_KEY, CoverConf
from .entity import KnxUiEntity, KnxUiEntityPlatformController, KnxYamlEntity
from .knx_module import KNXModule
from .schema import CoverSchema
from .storage.const import (
    CONF_ENTITY,
    CONF_GA_ANGLE,
    CONF_GA_POSITION_SET,
    CONF_GA_POSITION_STATE,
    CONF_GA_STEP,
    CONF_GA_STOP,
    CONF_GA_UP_DOWN,
)
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KNX cover platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.COVER,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiCover,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.COVER):
        entities.extend(
            KnxYamlCover(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.COVER):
        entities.extend(
            KnxUiCover(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxCover(CoverEntity):
    """Representation of a KNX cover."""

    _device: XknxCover

    def init_base(self) -> None:
        """Initialize common attributes - may be based on xknx device instance."""
        _supports_tilt = False
        self._attr_supported_features = (
            CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN
        )
        if self._device.supports_position or self._device.supports_stop:
            # when stop is supported, xknx travelcalculator can set position
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
        if self._device.step.writable:
            _supports_tilt = True
            self._attr_supported_features |= (
                CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.STOP_TILT
            )
        if self._device.supports_angle:
            _supports_tilt = True
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION
        if self._device.supports_stop:
            self._attr_supported_features |= CoverEntityFeature.STOP
            if _supports_tilt:
                self._attr_supported_features |= CoverEntityFeature.STOP_TILT

        self._attr_device_class = CoverDeviceClass.BLIND if _supports_tilt else None

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        # In KNX 0 is open, 100 is closed.
        if (pos := self._device.current_position()) is not None:
            return 100 - pos
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        # state shall be "unknown" when xknx travelcalculator is not initialized
        if self._device.current_position() is None:
            return None
        return self._device.is_closed()

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._device.is_opening()

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._device.is_closing()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._device.set_down()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.set_up()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        knx_position = 100 - kwargs[ATTR_POSITION]
        await self._device.set_position(knx_position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._device.stop()

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if (angle := self._device.current_angle()) is not None:
            return 100 - angle
        return None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        knx_tilt_position = 100 - kwargs[ATTR_TILT_POSITION]
        await self._device.set_angle(knx_tilt_position)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if self._device.angle.writable:
            await self._device.set_angle(0)
        else:
            await self._device.set_short_up()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if self._device.angle.writable:
            await self._device.set_angle(100)
        else:
            await self._device.set_short_down()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self._device.stop()


class KnxYamlCover(_KnxCover, KnxYamlEntity):
    """Representation of a KNX cover configured from YAML."""

    _device: XknxCover

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize the cover."""
        super().__init__(
            knx_module=knx_module,
            device=XknxCover(
                xknx=knx_module.xknx,
                name=config[CONF_NAME],
                group_address_long=config.get(CoverSchema.CONF_MOVE_LONG_ADDRESS),
                group_address_short=config.get(CoverSchema.CONF_MOVE_SHORT_ADDRESS),
                group_address_stop=config.get(CoverSchema.CONF_STOP_ADDRESS),
                group_address_position_state=config.get(
                    CoverSchema.CONF_POSITION_STATE_ADDRESS
                ),
                group_address_angle=config.get(CoverSchema.CONF_ANGLE_ADDRESS),
                group_address_angle_state=config.get(
                    CoverSchema.CONF_ANGLE_STATE_ADDRESS
                ),
                group_address_position=config.get(CoverSchema.CONF_POSITION_ADDRESS),
                travel_time_down=config[CoverConf.TRAVELLING_TIME_DOWN],
                travel_time_up=config[CoverConf.TRAVELLING_TIME_UP],
                invert_updown=config[CoverConf.INVERT_UPDOWN],
                invert_position=config[CoverConf.INVERT_POSITION],
                invert_angle=config[CoverConf.INVERT_ANGLE],
            ),
        )
        self.init_base()

        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = (
            f"{self._device.updown.group_address}_"
            f"{self._device.position_target.group_address}"
        )
        if custom_device_class := config.get(CONF_DEVICE_CLASS):
            self._attr_device_class = custom_device_class


def _create_ui_cover(xknx: XKNX, knx_config: ConfigType, name: str) -> XknxCover:
    """Return a KNX Light device to be used within XKNX."""

    conf = ConfigExtractor(knx_config)

    return XknxCover(
        xknx=xknx,
        name=name,
        group_address_long=conf.get_write_and_passive(CONF_GA_UP_DOWN),
        group_address_short=conf.get_write_and_passive(CONF_GA_STEP),
        group_address_stop=conf.get_write_and_passive(CONF_GA_STOP),
        group_address_position=conf.get_write_and_passive(CONF_GA_POSITION_SET),
        group_address_position_state=conf.get_state_and_passive(CONF_GA_POSITION_STATE),
        group_address_angle=conf.get_write(CONF_GA_ANGLE),
        group_address_angle_state=conf.get_state_and_passive(CONF_GA_ANGLE),
        travel_time_down=conf.get(CoverConf.TRAVELLING_TIME_DOWN),
        travel_time_up=conf.get(CoverConf.TRAVELLING_TIME_UP),
        invert_updown=conf.get(CoverConf.INVERT_UPDOWN, default=False),
        invert_position=conf.get(CoverConf.INVERT_POSITION, default=False),
        invert_angle=conf.get(CoverConf.INVERT_ANGLE, default=False),
        sync_state=conf.get(CONF_SYNC_STATE),
    )


class KnxUiCover(_KnxCover, KnxUiEntity):
    """Representation of a KNX cover configured from the UI."""

    _device: XknxCover

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize KNX cover."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        self._device = _create_ui_cover(
            knx_module.xknx, config[DOMAIN], config[CONF_ENTITY][CONF_NAME]
        )
        self.init_base()
