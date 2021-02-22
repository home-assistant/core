"""Exposures to KNX bus."""
from typing import Union

from xknx import XKNX
from xknx.devices import DateTime, ExposeSensor

from homeassistant.const import (
    CONF_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from .schema import ExposeSchema


@callback
def create_knx_exposure(
    hass: HomeAssistant, xknx: XKNX, config: ConfigType
) -> Union["KNXExposeSensor", "KNXExposeTime"]:
    """Create exposures from config."""
    expose_type = config.get(ExposeSchema.CONF_KNX_EXPOSE_TYPE)
    entity_id = config.get(CONF_ENTITY_ID)
    attribute = config.get(ExposeSchema.CONF_KNX_EXPOSE_ATTRIBUTE)
    default = config.get(ExposeSchema.CONF_KNX_EXPOSE_DEFAULT)
    address = config.get(ExposeSchema.CONF_KNX_EXPOSE_ADDRESS)

    exposure: Union["KNXExposeSensor", "KNXExposeTime"]
    if expose_type.lower() in ["time", "date", "datetime"]:
        exposure = KNXExposeTime(xknx, expose_type, address)
    else:
        exposure = KNXExposeSensor(
            hass,
            xknx,
            expose_type,
            entity_id,
            attribute,
            default,
            address,
        )
    exposure.async_register()
    return exposure


class KNXExposeSensor:
    """Object to Expose Home Assistant entity to KNX bus."""

    def __init__(self, hass, xknx, expose_type, entity_id, attribute, default, address):
        """Initialize of Expose class."""
        self.hass = hass
        self.xknx = xknx
        self.type = expose_type
        self.entity_id = entity_id
        self.expose_attribute = attribute
        self.expose_default = default
        self.address = address
        self.device = None
        self._remove_listener = None

    @callback
    def async_register(self):
        """Register listener."""
        if self.expose_attribute is not None:
            _name = self.entity_id + "__" + self.expose_attribute
        else:
            _name = self.entity_id
        self.device = ExposeSensor(
            self.xknx,
            name=_name,
            group_address=self.address,
            value_type=self.type,
        )
        self._remove_listener = async_track_state_change_event(
            self.hass, [self.entity_id], self._async_entity_changed
        )

    @callback
    def shutdown(self) -> None:
        """Prepare for deletion."""
        if self._remove_listener is not None:
            self._remove_listener()
        if self.device is not None:
            self.device.shutdown()

    async def _async_entity_changed(self, event):
        """Handle entity change."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        if new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        if self.expose_attribute is None:
            await self._async_set_knx_value(new_state.state)
            return

        new_attribute = new_state.attributes.get(self.expose_attribute)
        old_state = event.data.get("old_state")

        if old_state is not None:
            old_attribute = old_state.attributes.get(self.expose_attribute)
            if old_attribute == new_attribute:
                # don't send same value sequentially
                return
        await self._async_set_knx_value(new_attribute)

    async def _async_set_knx_value(self, value):
        """Set new value on xknx ExposeSensor."""
        if value is None:
            if self.expose_default is None:
                return
            value = self.expose_default

        if self.type == "binary":
            if value == STATE_ON:
                value = True
            elif value == STATE_OFF:
                value = False

        await self.device.set(value)


class KNXExposeTime:
    """Object to Expose Time/Date object to KNX bus."""

    def __init__(self, xknx: XKNX, expose_type: str, address: str):
        """Initialize of Expose class."""
        self.xknx = xknx
        self.expose_type = expose_type
        self.address = address
        self.device = None

    @callback
    def async_register(self):
        """Register listener."""
        self.device = DateTime(
            self.xknx,
            name=self.expose_type.capitalize(),
            broadcast_type=self.expose_type.upper(),
            localtime=True,
            group_address=self.address,
        )

    @callback
    def shutdown(self):
        """Prepare for deletion."""
        if self.device is not None:
            self.device.shutdown()
