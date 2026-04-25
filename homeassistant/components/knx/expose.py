"""Expose Home Assistant entity states to KNX."""

from __future__ import annotations

from asyncio import TaskGroup
from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from xknx import XKNX
from xknx.devices import DateDevice, DateTimeDevice, ExposeSensor, TimeDevice
from xknx.dpt import DPTBase, DPTNumeric, DPTString
from xknx.dpt.dpt_1 import DPT1BitEnum, DPTSwitch
from xknx.exceptions import ConversionError
from xknx.telegram.address import (
    GroupAddress,
    InternalGroupAddress,
    parse_device_group_address,
)

from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util import dt as dt_util

from .const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from .schema import ExposeSchema

if TYPE_CHECKING:
    from .storage.time_server import KNXTimeServerStoreModel

_LOGGER = logging.getLogger(__name__)


@callback
def create_knx_exposure(
    hass: HomeAssistant, xknx: XKNX, config: ConfigType
) -> KnxExposeEntity | KnxExposeTime:
    """Create single exposure."""
    expose_type = config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]
    exposure: KnxExposeEntity | KnxExposeTime
    if (
        isinstance(expose_type, str)
        and expose_type.lower() in ExposeSchema.EXPOSE_TIME_TYPES
    ):
        exposure = KnxExposeTime(
            xknx=xknx,
            options=_yaml_config_to_expose_time_options(config),
        )
    else:
        exposure = KnxExposeEntity(
            hass=hass,
            xknx=xknx,
            entity_id=config[CONF_ENTITY_ID],
            options=(_yaml_config_to_expose_options(config),),
        )
    exposure.async_register()
    return exposure


@callback
def create_combined_knx_exposure(
    hass: HomeAssistant, xknx: XKNX, configs: list[ConfigType]
) -> list[KnxExposeEntity | KnxExposeTime]:
    """Create exposures from YAML config combined by entity_id."""
    exposures: list[KnxExposeEntity | KnxExposeTime] = []
    entity_exposure_map: dict[str, list[KnxExposeOptions]] = {}

    for config in configs:
        value_type = config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]
        if value_type.lower() in ExposeSchema.EXPOSE_TIME_TYPES:
            time_exposure = KnxExposeTime(
                xknx=xknx,
                options=_yaml_config_to_expose_time_options(config),
            )
            time_exposure.async_register()
            exposures.append(time_exposure)
            continue

        entity_id = config[CONF_ENTITY_ID]
        option = _yaml_config_to_expose_options(config)
        entity_exposure_map.setdefault(entity_id, []).append(option)

    for entity_id, options in entity_exposure_map.items():
        entity_exposure = KnxExposeEntity(
            hass=hass,
            xknx=xknx,
            entity_id=entity_id,
            options=options,
        )
        entity_exposure.async_register()
        exposures.append(entity_exposure)
    return exposures


@dataclass(slots=True)
class KnxExposeOptions:
    """Options for KNX Expose."""

    attribute: str | None
    group_address: GroupAddress | InternalGroupAddress
    dpt: type[DPTBase]
    respond_to_read: bool
    cooldown: float
    periodic_send: float
    default: Any | None
    value_template: Template | None


def _yaml_config_to_expose_options(config: ConfigType) -> KnxExposeOptions:
    """Convert single yaml expose config to KnxExposeOptions."""
    value_type = config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]
    dpt: type[DPTBase]
    if value_type == "binary":
        # HA yaml expose flag for DPT-1 (no explicit DPT 1 definitions in xknx back then)
        dpt = DPTSwitch
    else:
        dpt = DPTBase.parse_transcoder(config[ExposeSchema.CONF_KNX_EXPOSE_TYPE])  # type: ignore[assignment]  # checked by schema validation
    ga = parse_device_group_address(config[KNX_ADDRESS])
    cooldown_seconds = config[ExposeSchema.CONF_KNX_EXPOSE_COOLDOWN].total_seconds()
    periodic_send_seconds = config[
        ExposeSchema.CONF_KNX_EXPOSE_PERIODIC_SEND
    ].total_seconds()
    return KnxExposeOptions(
        attribute=config.get(ExposeSchema.CONF_KNX_EXPOSE_ATTRIBUTE),
        group_address=ga,
        dpt=dpt,
        respond_to_read=config[CONF_RESPOND_TO_READ],
        cooldown=cooldown_seconds,
        periodic_send=periodic_send_seconds,
        default=config.get(ExposeSchema.CONF_KNX_EXPOSE_DEFAULT),
        value_template=config.get(CONF_VALUE_TEMPLATE),
    )


class KnxExposeEntity:
    """Expose Home Assistant entity values to KNX bus."""

    def __init__(
        self,
        hass: HomeAssistant,
        xknx: XKNX,
        entity_id: str,
        options: Iterable[KnxExposeOptions],
    ) -> None:
        """Initialize KnxExposeEntity class."""
        self.hass = hass
        self.xknx = xknx
        self.entity_id = entity_id

        self._remove_listener: Callable[[], None] | None = None
        self._exposures = tuple(
            (
                option,
                ExposeSensor(
                    xknx=self.xknx,
                    name=f"{self.entity_id} {option.attribute or 'state'}",
                    group_address=option.group_address,
                    respond_to_read=option.respond_to_read,
                    value_type=option.dpt,
                    cooldown=option.cooldown,
                    periodic_send=option.periodic_send,
                ),
            )
            for option in options
        )

    @property
    def name(self) -> str:
        """Return name of the expose entity."""
        expose_names = [opt.attribute or "state" for opt, _ in self._exposures]
        return f"{self.entity_id}__{'__'.join(expose_names)}"

    @callback
    def async_register(self) -> None:
        """Register listener and XKNX devices."""
        self._remove_listener = async_track_state_change_event(
            self.hass, [self.entity_id], self._async_entity_changed
        )
        for _option, xknx_expose in self._exposures:
            self.xknx.devices.async_add(xknx_expose)
        self._init_expose_state()

    @callback
    def _init_expose_state(self) -> None:
        """Initialize state of all exposures."""
        init_state = self.hass.states.get(self.entity_id)
        for option, xknx_expose in self._exposures:
            state_value = self._get_expose_value(init_state, option)
            try:
                xknx_expose.sensor_value.value = state_value
            except ConversionError:
                _LOGGER.exception(
                    "Error setting value %s for expose sensor %s",
                    state_value,
                    xknx_expose.name,
                )

    @callback
    def async_remove(self) -> None:
        """Prepare for deletion."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        for _option, xknx_expose in self._exposures:
            self.xknx.devices.async_remove(xknx_expose)

    def _get_expose_value(
        self, state: State | None, option: KnxExposeOptions
    ) -> bool | int | float | str | None:
        """Extract value from state for a specific option."""
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            if option.default is None:
                return None
            value = option.default
        elif option.attribute is not None:
            _attr = state.attributes.get(option.attribute)
            value = _attr if _attr is not None else option.default
        else:
            value = state.state

        if option.value_template is not None:
            try:
                value = option.value_template.async_render_with_possible_json_value(
                    value, error_value=None
                )
            except (TemplateError, TypeError, ValueError) as err:
                _LOGGER.warning(
                    "Error rendering value template for KNX expose %s %s %s: %s",
                    self.entity_id,
                    option.attribute or "state",
                    option.value_template.template,
                    err,
                )
                return None

        if issubclass(option.dpt, DPT1BitEnum):
            if value in (1, STATE_ON, "True"):
                return True
            if value in (0, STATE_OFF, "False"):
                return False

        # Handle numeric and string DPT conversions
        if value is not None:
            try:
                if issubclass(option.dpt, DPTNumeric):
                    return float(value)
                if issubclass(option.dpt, DPTString):
                    # DPT 16.000 only allows up to 14 Bytes
                    return str(value)[:14]
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    'Could not expose %s %s value "%s" to KNX: Conversion failed: %s',
                    self.entity_id,
                    option.attribute or "state",
                    value,
                    err,
                )
                return None
        return value  # type: ignore[no-any-return]

    async def _async_entity_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle entity change for all options."""
        new_state = event.data["new_state"]
        async with TaskGroup() as tg:
            for option, xknx_expose in self._exposures:
                expose_value = self._get_expose_value(new_state, option)
                if expose_value is None:
                    continue
                tg.create_task(self._async_set_knx_value(xknx_expose, expose_value))

    async def _async_set_knx_value(
        self, xknx_expose: ExposeSensor, value: StateType
    ) -> None:
        """Set new value on xknx ExposeSensor."""
        try:
            await xknx_expose.set(value, skip_unchanged=True)
        except ConversionError as err:
            _LOGGER.warning(
                'Could not expose %s value "%s" to KNX: %s',
                xknx_expose.name,
                value,
                err,
            )


@dataclass
class KnxExposeTimeOptions:
    """Options for KNX Expose time."""

    device_cls: type[DateDevice | DateTimeDevice | TimeDevice]
    group_address: GroupAddress | InternalGroupAddress
    name: str


def _yaml_config_to_expose_time_options(config: ConfigType) -> KnxExposeTimeOptions:
    """Convert single yaml expose time config to KnxExposeTimeOptions."""
    ga = parse_device_group_address(config[KNX_ADDRESS])
    expose_type: str = config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]
    xknx_device_cls: type[DateDevice | DateTimeDevice | TimeDevice]
    match expose_type.lower():
        case ExposeSchema.CONF_DATE:
            xknx_device_cls = DateDevice
        case ExposeSchema.CONF_DATETIME:
            xknx_device_cls = DateTimeDevice
        case ExposeSchema.CONF_TIME:
            xknx_device_cls = TimeDevice
    return KnxExposeTimeOptions(
        name=expose_type.capitalize(),
        group_address=ga,
        device_cls=xknx_device_cls,
    )


@callback
def create_time_server_exposures(
    xknx: XKNX,
    config: KNXTimeServerStoreModel,
) -> list[KnxExposeTime]:
    """Create exposures from UI config store time server config."""
    exposures: list[KnxExposeTime] = []
    device_cls: type[DateDevice | DateTimeDevice | TimeDevice]
    for expose_type, data in config.items():
        if not data or (ga := data.get("write")) is None:  # type: ignore[attr-defined]
            continue
        match expose_type:
            case "time":
                device_cls = TimeDevice
            case "date":
                device_cls = DateDevice
            case "datetime":
                device_cls = DateTimeDevice
            case _:
                continue
        exposures.append(
            KnxExposeTime(
                xknx=xknx,
                options=KnxExposeTimeOptions(
                    name=f"timeserver_{expose_type}",
                    group_address=parse_device_group_address(ga),
                    device_cls=device_cls,
                ),
            )
        )
    for exposure in exposures:
        exposure.async_register()
    return exposures


class KnxExposeTime:
    """Object to Expose Time/Date object to KNX bus."""

    __slots__ = ("device", "xknx")

    def __init__(self, xknx: XKNX, options: KnxExposeTimeOptions) -> None:
        """Initialize of Expose class."""
        self.xknx = xknx
        self.device = options.device_cls(
            self.xknx,
            name=options.name,
            localtime=dt_util.get_default_time_zone(),
            group_address=options.group_address,
        )

    @property
    def name(self) -> str:
        """Return name of the time expose object."""
        return f"expose_{self.device.name}"

    @callback
    def async_register(self) -> None:
        """Register listener."""
        self.xknx.devices.async_add(self.device)

    @callback
    def async_remove(self) -> None:
        """Prepare for deletion."""
        self.xknx.devices.async_remove(self.device)
