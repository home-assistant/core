"""Support for KNX cover entities."""

from typing import Any, override

from xknx import XKNX
from xknx.devices import (
    Cover as XknxCover,
    Device as XknxDevice,
    ExposeSensor as XknxExposeSensor,
)

from homeassistant import config_entries
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
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

from .const import CONF_SYNC_STATE, DOMAIN, KNX_MODULE_KEY, CoverConf
from .entity import (
    KnxUiEntity,
    KnxUiEntityPlatformController,
    KnxYamlEntity,
    build_yaml_unique_id,
)
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


# Minimum time between two position telegrams while travelling. Without it every
# travel calculator update would be sent - about one telegram per second per cover.
POSITION_SEND_COOLDOWN = 2.0


def _first_ga(group_addresses: str | list[str]) -> str:
    """Return one group address - the YAML validator yields a list.

    Only the first entry is used: a display value has exactly one sender, so
    passive addresses make no sense here.
    """
    if isinstance(group_addresses, list):
        return group_addresses[0]
    return group_addresses


def _create_position_publisher(
    xknx: XKNX, name: str, group_address: Any, cooldown: float
) -> XknxExposeSensor:
    """Return an xknx device publishing the calculated position to the bus.

    Used when no actuator reports the position: then the travel calculator is the
    only source and displays have no other way to learn it. The caller must not
    register the same address as position_state - Home Assistant would read its
    own telegram back as actuator feedback and rewind the travel calculator.
    """
    return XknxExposeSensor(
        xknx,
        name=f"{name} Position",
        group_address=group_address,
        value_type="percent",
        cooldown=cooldown,
        respond_to_read=True,
    )


class _KnxCover(CoverEntity, RestoreEntity):
    """Representation of a KNX cover."""

    _device: XknxCover
    _position_publisher: XknxExposeSensor | None = None
    _published_position: int | None = None

    def init_base(self) -> None:
        """Initialize common attributes - may be based on xknx device instance."""
        self._attr_supported_features = (
            CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN
        )
        if self._device.supports_position or self._device.supports_stop:
            # when stop is supported, xknx travelcalculator can set position
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
        _supports_tilt = False
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

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last known position and tilt.

        For readable group addresses this bridges the gap until the bus read
        response arrives; for non-readable ones it is the only source of state.
        """
        await super().async_added_to_hass()
        if self._position_publisher is not None:
            self._device.register_device_updated_cb(self._publish_position)
            self._position_publisher.xknx.devices.async_add(self._position_publisher)
        if (last_state := await self.async_get_last_state()) is None or (
            last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            return
        if (position := last_state.attributes.get(ATTR_CURRENT_POSITION)) is not None:
            # In KNX 0 is open, 100 is closed.
            self._device.travelcalculator.set_position(100 - position)
        if (
            tilt_position := last_state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        ) is not None:
            self._device.angle.value = 100 - tilt_position
        if (
            self._position_publisher is not None
            and (position := self._payload_position()) is not None
        ):
            # seed the publisher so it can answer a read before the first travel
            self._published_position = position
            await self._position_publisher.set(position)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Remove the position publisher from xknx."""
        if self._position_publisher is not None:
            self._device.unregister_device_updated_cb(self._publish_position)
            self._position_publisher.xknx.devices.async_remove(self._position_publisher)
            self._position_publisher = None
        await super().async_will_remove_from_hass()

    def _payload_position(self) -> int | None:
        """Return the position in the group address value domain.

        The travel calculator counts 0 as open. For an actuator configured with
        invert_position the group address counts the other way round - xknx does
        that in the RemoteValueScaling ranges, which this device does not use.
        """
        if (position := self._device.current_position()) is None:
            return None
        if self._device.position_current.range_from == 100:
            return 100 - position
        return position

    def _publish_position(self, device: XknxDevice) -> None:
        """Publish the position after the travel calculator advanced.

        Registered as an additional device callback rather than overriding
        after_update_callback: that method comes from the KNX entity mixin, which
        is only applied in the concrete YAML and UI classes.

        The cached value skips a repeated publish while the cover stands still.
        It is deliberately read again when the task runs, so that closely
        following updates collapse into one telegram carrying the newest
        position - skip_unchanged then drops the trailing duplicates.
        """
        if (
            self._position_publisher is not None
            and (position := self._payload_position()) is not None
            and position != self._published_position
        ):
            self._published_position = position
            self.hass.async_create_task(self._async_publish_position())

    async def _async_publish_position(self) -> None:
        """Send the cached position unless the entity was removed meanwhile.

        The task outlives async_will_remove_from_hass, and sending goes through
        the telegram queue rather than the device list - without this check a
        reload during a travel could still put a stale value on the bus.
        """
        if self._position_publisher is None or self._published_position is None:
            return
        await self._position_publisher.set(
            self._published_position, skip_unchanged=True
        )

    @property
    @override
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        # Without a known position or movement value, the position is only
        # read from the restored state in the travelcalculator. This prevents
        # out-of-sync positions from disabling controls in the UI.
        return (
            self._device.position_current.value is None
            and self._device.position_target.value is None
            and self._device.updown.value is None
        )

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        # In KNX 0 is open, 100 is closed.
        if (pos := self._device.current_position()) is not None:
            return 100 - pos
        return None

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        # state shall be "unknown" when xknx travelcalculator is not initialized
        if self._device.current_position() is None:
            return None
        return self._device.is_closed()

    @property
    @override
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._device.is_opening()

    @property
    @override
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._device.is_closing()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._device.set_down()

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.set_up()

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        knx_position = 100 - kwargs[ATTR_POSITION]
        await self._device.set_position(knx_position)

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._device.stop()

    @property
    @override
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if (angle := self._device.current_angle()) is not None:
            return 100 - angle
        return None

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        knx_tilt_position = 100 - kwargs[ATTR_TILT_POSITION]
        await self._device.set_angle(knx_tilt_position)

    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if self._device.angle.writable:
            await self._device.set_angle(0)
        else:
            await self._device.set_short_up()

    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if self._device.angle.writable:
            await self._device.set_angle(100)
        else:
            await self._device.set_short_down()

    @override
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self._device.stop()


class KnxYamlCover(_KnxCover, KnxYamlEntity):
    """Representation of a KNX cover configured from YAML."""

    _device: XknxCover

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize the cover."""
        self._device = XknxCover(
            xknx=knx_module.xknx,
            name=config[CONF_NAME],
            group_address_long=config.get(CoverSchema.CONF_MOVE_LONG_ADDRESS),
            group_address_short=config.get(CoverSchema.CONF_MOVE_SHORT_ADDRESS),
            group_address_stop=config.get(CoverSchema.CONF_STOP_ADDRESS),
            group_address_position_state=(
                None
                if config[CoverConf.POSITION_STATE_SEND]
                else config.get(CoverSchema.CONF_POSITION_STATE_ADDRESS)
            ),
            group_address_angle=config.get(CoverSchema.CONF_ANGLE_ADDRESS),
            group_address_angle_state=config.get(CoverSchema.CONF_ANGLE_STATE_ADDRESS),
            group_address_position=config.get(CoverSchema.CONF_POSITION_ADDRESS),
            travel_time_down=config[CoverConf.TRAVELLING_TIME_DOWN],
            travel_time_up=config[CoverConf.TRAVELLING_TIME_UP],
            invert_updown=config[CoverConf.INVERT_UPDOWN],
            invert_position=config[CoverConf.INVERT_POSITION],
            invert_angle=config[CoverConf.INVERT_ANGLE],
        )
        super().__init__(
            knx_module=knx_module,
            unique_id=build_yaml_unique_id(
                self._device.updown.group_address,
                self._device.position_target.group_address,
            ),
            entity_config=config,
        )
        self.init_base()
        if config[CoverConf.POSITION_STATE_SEND] and (
            state_ga := config.get(CoverSchema.CONF_POSITION_STATE_ADDRESS)
        ):
            self._position_publisher = _create_position_publisher(
                knx_module.xknx,
                name=config[CONF_NAME],
                group_address=_first_ga(state_ga),
                cooldown=POSITION_SEND_COOLDOWN,
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
        group_address_position_state=(
            None
            if conf.get(CoverConf.POSITION_STATE_SEND)
            else conf.get_state_and_passive(CONF_GA_POSITION_STATE)
        ),
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
        knx_conf = ConfigExtractor(config[DOMAIN])
        if (
            knx_conf.get(CoverConf.POSITION_STATE_SEND)
            and (state_ga := knx_conf.get_state(CONF_GA_POSITION_STATE)) is not None
        ):
            self._position_publisher = _create_position_publisher(
                knx_module.xknx,
                name=config[CONF_ENTITY][CONF_NAME],
                group_address=state_ga,
                cooldown=POSITION_SEND_COOLDOWN,
            )
        self.init_base()
