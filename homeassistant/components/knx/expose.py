"""Exposures to KNX bus."""
from __future__ import annotations

from collections.abc import Callable
import logging

from xknx import XKNX
from xknx.devices import DateTime, ExposeSensor
from xknx.dpt import DPTNumeric, DPTString
from xknx.exceptions import ConversionError
from xknx.remote_value import RemoteValueSensor

from homeassistant.const import (
    CONF_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType, EventType, StateType

from .const import CONF_RESPOND_TO_READ, KNX_ADDRESS
from .schema import ExposeSchema

_LOGGER = logging.getLogger(__name__)


@callback
def create_knx_exposure(
    hass: HomeAssistant, xknx: XKNX, config: ConfigType
) -> KNXExposeSensor | KNXExposeTime:
    """Create exposures from config."""

    expose_type = config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]

    exposure: KNXExposeSensor | KNXExposeTime
    if (
        isinstance(expose_type, str)
        and expose_type.lower() in ExposeSchema.EXPOSE_TIME_TYPES
    ):
        exposure = KNXExposeTime(
            xknx=xknx,
            config=config,
        )
    else:
        exposure = KNXExposeSensor(
            hass,
            xknx=xknx,
            config=config,
        )
    return exposure


class KNXExposeSensor:
    """Object to Expose Home Assistant entity to KNX bus."""

    def __init__(
        self,
        hass: HomeAssistant,
        xknx: XKNX,
        config: ConfigType,
    ) -> None:
        """Initialize of Expose class."""
        self.hass = hass
        self.xknx = xknx

        self.entity_id: str = config[CONF_ENTITY_ID]
        self.expose_attribute: str | None = config.get(
            ExposeSchema.CONF_KNX_EXPOSE_ATTRIBUTE
        )
        self.expose_default = config.get(ExposeSchema.CONF_KNX_EXPOSE_DEFAULT)
        self.expose_type: int | str = config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]

        self._remove_listener: Callable[[], None] | None = None
        self.device: ExposeSensor = self.async_register(config)
        self._init_expose_state()

    @callback
    def async_register(self, config: ConfigType) -> ExposeSensor:
        """Register listener."""
        if self.expose_attribute is not None:
            _name = self.entity_id + "__" + self.expose_attribute
        else:
            _name = self.entity_id
        device = ExposeSensor(
            xknx=self.xknx,
            name=_name,
            group_address=config[KNX_ADDRESS],
            respond_to_read=config[CONF_RESPOND_TO_READ],
            value_type=self.expose_type,
            cooldown=config[ExposeSchema.CONF_KNX_EXPOSE_COOLDOWN],
        )
        self._remove_listener = async_track_state_change_event(
            self.hass, [self.entity_id], self._async_entity_changed
        )
        return device

    @callback
    def _init_expose_state(self) -> None:
        """Initialize state of the exposure."""
        init_state = self.hass.states.get(self.entity_id)
        state_value = self._get_expose_value(init_state)
        try:
            self.device.sensor_value.value = state_value
        except ConversionError:
            _LOGGER.exception("Error during sending of expose sensor value")

    @callback
    def shutdown(self) -> None:
        """Prepare for deletion."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        self.device.shutdown()

    def _get_expose_value(self, state: State | None) -> bool | int | float | str | None:
        """Extract value from state."""
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            value = self.expose_default
        elif self.expose_attribute is not None:
            _attr = state.attributes.get(self.expose_attribute)
            value = _attr if _attr is not None else self.expose_default
        else:
            value = state.state

        if self.expose_type == "binary":
            if value in (1, STATE_ON, "True"):
                return True
            if value in (0, STATE_OFF, "False"):
                return False
        if (
            value is not None
            and isinstance(self.device.sensor_value, RemoteValueSensor)
            and issubclass(self.device.sensor_value.dpt_class, DPTNumeric)
        ):
            return float(value)
        if (
            value is not None
            and isinstance(self.device.sensor_value, RemoteValueSensor)
            and issubclass(self.device.sensor_value.dpt_class, DPTString)
        ):
            # DPT 16.000 only allows up to 14 Bytes
            return str(value)[:14]
        return value

    async def _async_entity_changed(
        self, event: EventType[EventStateChangedData]
    ) -> None:
        """Handle entity change."""
        new_state = event.data["new_state"]
        if (new_value := self._get_expose_value(new_state)) is None:
            return
        old_state = event.data["old_state"]
        # don't use default value for comparison on first state change (old_state is None)
        old_value = self._get_expose_value(old_state) if old_state is not None else None
        # don't send same value sequentially
        if new_value != old_value:
            await self._async_set_knx_value(new_value)

    async def _async_set_knx_value(self, value: StateType) -> None:
        """Set new value on xknx ExposeSensor."""
        try:
            await self.device.set(value)
        except ConversionError as err:
            _LOGGER.warning(
                'Could not expose %s %s value "%s" to KNX: %s',
                self.entity_id,
                self.expose_attribute or "state",
                value,
                err,
            )


class KNXExposeTime:
    """Object to Expose Time/Date object to KNX bus."""

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of Expose class."""
        self.xknx = xknx
        self.device: DateTime = self.async_register(config)

    @callback
    def async_register(self, config: ConfigType) -> DateTime:
        """Register listener."""
        expose_type = config[ExposeSchema.CONF_KNX_EXPOSE_TYPE]
        return DateTime(
            self.xknx,
            name=expose_type.capitalize(),
            broadcast_type=expose_type.upper(),
            localtime=True,
            group_address=config[KNX_ADDRESS],
        )

    @callback
    def shutdown(self) -> None:
        """Prepare for deletion."""
        self.device.shutdown()
