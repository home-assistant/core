"""Expose Home Assistant entity states to KNX."""

from asyncio import TaskGroup
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, NamedTuple

from xknx import XKNX
from xknx.core.telegram_queue import TelegramQueue
from xknx.devices import DateDevice, DateTimeDevice, ExposeSensor, TimeDevice
from xknx.dpt import DPTArray, DPTBase, DPTBinary, DPTNumeric, DPTString
from xknx.dpt.dpt_1 import DPT1BitEnum, DPTSwitch
from xknx.exceptions import ConversionError, CouldNotParseTelegram
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.address import (
    GroupAddress,
    IndividualAddress,
    InternalGroupAddress,
    parse_device_group_address,
)
from xknx.telegram.apci import GroupValueWrite

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_VALUE_TEMPLATE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
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
    split_entity_id,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util import dt as dt_util

from .const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from .dpt import ha_dpt_class
from .schema import ExposeSchema

if TYPE_CHECKING:
    from .storage.time_server import KNXTimeServerStoreModel

_LOGGER = logging.getLogger(__name__)

# write-back target per (DPT value kind, entity domain): (service domain, service, field)
_WRITE_BACK_DISPATCH: dict[tuple[str, str], tuple[str, str, str]] = {
    ("numeric", "number"): ("number", "set_value", "value"),
    ("numeric", "input_number"): ("input_number", "set_value", "value"),
    ("string", "text"): ("text", "set_value", "value"),
    ("string", "input_text"): ("input_text", "set_value", "value"),
}


class _WriteBackCall(NamedTuple):
    """Resolved write-back for an incoming telegram: value + service to call."""

    echo_value: bool | int | float | str
    domain: str
    service: str
    data: dict[str, Any]


def write_back_target_supported(dpt: type[DPTBase], entity_domain: str) -> bool:
    """Return whether write-back can reach the given entity domain for this DPT."""
    if issubclass(dpt, DPT1BitEnum):
        return True  # binary targets are checked at runtime via has_service
    return (ha_dpt_class(dpt), entity_domain) in _WRITE_BACK_DISPATCH


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
    write_back: bool = False
    source_whitelist: frozenset[str] = frozenset()


def _yaml_config_to_expose_options(config: ConfigType) -> KnxExposeOptions:
    """Convert single yaml expose config to KnxExposeOptions."""
    value_type = config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]
    dpt: type[DPTBase]
    if value_type == "binary":
        # HA yaml expose flag for DPT-1
        # (no explicit DPT 1 definitions in xknx back then)
        dpt = DPTSwitch
    else:
        dpt = DPTBase.parse_transcoder(  # type: ignore[assignment]
            config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]
        )
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
        write_back=config[ExposeSchema.CONF_KNX_EXPOSE_WRITE_BACK],
        source_whitelist=frozenset(
            str(IndividualAddress(ia))
            for ia in config[ExposeSchema.CONF_KNX_EXPOSE_SOURCE_WHITELIST]
        ),
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
        self._telegram_cb_handle: TelegramQueue.Callback | None = None
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
        write_back_addresses: list[GroupAddress | InternalGroupAddress] = []
        for option, _xknx_expose in self._exposures:
            if not option.write_back:
                continue
            write_back_addresses.append(option.group_address)
            if not option.source_whitelist:
                _LOGGER.warning(
                    "KNX expose %s has write_back enabled without a source_whitelist; "
                    "any KNX device may change its state",
                    self.entity_id,
                )
        if write_back_addresses:
            self._telegram_cb_handle = (
                self.xknx.telegram_queue.register_telegram_received_cb(
                    self._telegram_received_cb,
                    group_addresses=write_back_addresses,
                    match_for_outgoing=False,
                )
            )
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
        if self._telegram_cb_handle is not None:
            self.xknx.telegram_queue.unregister_telegram_received_cb(
                self._telegram_cb_handle
            )
            self._telegram_cb_handle = None
        for _option, xknx_expose in self._exposures:
            self.xknx.devices.async_remove(xknx_expose)

    def _telegram_received_cb(self, telegram: Telegram) -> None:
        """Change the exposed entity from a whitelisted incoming GroupValueWrite."""
        if telegram.direction is not TelegramDirection.INCOMING:
            return
        if (
            not isinstance(telegram.payload, GroupValueWrite)
            or telegram.payload.value is None
        ):
            return
        for option, xknx_expose in self._exposures:
            if (
                not option.write_back
                or option.group_address != telegram.destination_address
            ):
                continue
            if (
                option.source_whitelist
                and str(telegram.source_address) not in option.source_whitelist
            ):
                return
            call = self._write_back_service_call(option, telegram.payload.value)
            if call is None:
                return
            # Reflect the received value and pre-seed the ExposeSensor's last-sent
            # payload so the entity state change we trigger re-encodes identically
            # and is skipped by skip_unchanged. xknx exposes no public API for this;
            # guard the private attribute so a future xknx change surfaces as a
            # warning instead of silently echoing the value back onto the bus.
            with suppress(ConversionError):
                xknx_expose.sensor_value.value = call.echo_value
            if hasattr(xknx_expose, "_payload_after_cooldown"):
                xknx_expose._payload_after_cooldown = telegram.payload.value  # noqa: SLF001
            else:
                _LOGGER.warning(
                    "KNX expose %s: cannot suppress write_back echo (unexpected xknx "
                    "internals); the value may be re-sent to the bus",
                    self.entity_id,
                )
            self.hass.async_create_task(
                self.hass.services.async_call(
                    call.domain, call.service, call.data, blocking=False
                ),
                f"KNX expose write_back {self.entity_id}",
            )
            return

    def _write_back_service_call(
        self, option: KnxExposeOptions, payload: DPTBinary | DPTArray
    ) -> _WriteBackCall | None:
        """Map an incoming payload to the write-back service call, or None."""
        entity_domain = split_entity_id(self.entity_id)[0]
        if issubclass(option.dpt, DPT1BitEnum):
            try:
                value = bool(option.dpt.from_knx(payload).value)
            except (ConversionError, CouldNotParseTelegram) as err:
                _LOGGER.warning(
                    "Could not decode incoming telegram for KNX expose %s: %s",
                    self.entity_id,
                    err,
                )
                return None
            service = SERVICE_TURN_ON if value else SERVICE_TURN_OFF
            if not self.hass.services.has_service(entity_domain, service):
                _LOGGER.warning(
                    "KNX expose write_back to %s: %s does not support %s",
                    self.entity_id,
                    entity_domain,
                    service,
                )
                return None
            return _WriteBackCall(
                value, entity_domain, service, {ATTR_ENTITY_ID: self.entity_id}
            )
        mapping = _WRITE_BACK_DISPATCH.get((ha_dpt_class(option.dpt), entity_domain))
        if mapping is None:
            _LOGGER.warning(
                "KNX expose write_back to %s: unsupported target for the configured DPT",
                self.entity_id,
            )
            return None
        try:
            value = option.dpt.from_knx(payload)
        except (ConversionError, CouldNotParseTelegram) as err:
            _LOGGER.warning(
                "Could not decode incoming telegram for KNX expose %s: %s",
                self.entity_id,
                err,
            )
            return None
        service_domain, service, field = mapping
        data = {ATTR_ENTITY_ID: self.entity_id, field: value}
        return _WriteBackCall(value, service_domain, service, data)

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
                    # DPT 16 only allows up to 14 chars, DPT 4 a single char
                    return str(value)[: option.dpt.payload_length]
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
