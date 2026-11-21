"""Lightbulb service of an accessory, driven by a linked light entity."""

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    LightEntityCapabilityAttribute,
    LightEntityStateAttribute,
    LightService,
    LightServiceArgument,
    brightness_supported,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJobType,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CHAR_BRIGHTNESS,
    CHAR_CONFIGURED_NAME,
    CHAR_NAME,
    CHAR_ON,
    CONF_LINKED_LIGHT,
    SERV_LIGHTBULB,
)
from .util import cleanup_name_for_homekit

if TYPE_CHECKING:
    from .accessories import HomeAccessory

_LOGGER = logging.getLogger(__name__)


class LinkedLight:
    """Lightbulb service added to an accessory and driven by a light entity.

    Lets a device with a built-in light, such as a ceiling fan with a light
    kit, show as one accessory in the Home app instead of two.
    """

    def __init__(self, accessory: HomeAccessory, entity_id: str, state: State) -> None:
        """Add the Lightbulb service to the accessory."""
        self._accessory = accessory
        self.entity_id = entity_id
        color_modes = (
            state.attributes.get(LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES)
            or []
        )
        chars = [CHAR_NAME, CHAR_CONFIGURED_NAME]
        if brightness_supported(color_modes):
            chars.append(CHAR_BRIGHTNESS)
        serv_light = accessory.add_preload_service(
            SERV_LIGHTBULB, chars, unique_id=entity_id
        )
        name = cleanup_name_for_homekit(state.name)
        serv_light.configure_char(CHAR_NAME, value=name)
        serv_light.configure_char(CHAR_CONFIGURED_NAME, value=name)
        self.char_on = serv_light.configure_char(CHAR_ON, value=False)
        self.char_brightness = None
        if CHAR_BRIGHTNESS in chars:
            # 0 is a special value (off) in HomeKit, so start at an
            # arbitrary non-zero value until the state is read.
            self.char_brightness = serv_light.configure_char(CHAR_BRIGHTNESS, value=100)
        serv_light.setter_callback = self._set_chars
        self._async_update_state(state)

    @callback
    def async_subscribe(self) -> CALLBACK_TYPE:
        """Follow the light entity, starting from its current state."""
        self._async_update_state(self._accessory.hass.states.get(self.entity_id))
        return async_track_state_change_event(
            self._accessory.hass,
            [self.entity_id],
            self._async_update_event,
            job_type=HassJobType.Callback,
        )

    @callback
    def _async_update_event(self, event: Event[EventStateChangedData]) -> None:
        """Handle a state change of the light entity."""
        new_state = event.data["new_state"]
        old_state = event.data["old_state"]
        if (
            new_state
            and old_state
            and STATE_UNAVAILABLE not in (old_state.state, new_state.state)
            and old_state.attributes.get(
                LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES
            )
            != new_state.attributes.get(
                LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES
            )
        ):
            self._accessory.async_reload()
            return
        self._async_update_state(new_state)

    @callback
    def _async_update_state(self, new_state: State | None) -> None:
        """Update the Lightbulb service from the light state."""
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        is_on = new_state.state == STATE_ON
        self.char_on.set_value(is_on)
        if self.char_brightness is None:
            return
        brightness = new_state.attributes.get(LightEntityStateAttribute.BRIGHTNESS)
        if not isinstance(brightness, (int, float)):
            return
        brightness_pct = round(brightness / 255 * 100)
        # 0 means off in HomeKit, so an on light at 0 is shown at 1 %
        if brightness_pct == 0 and is_on:
            brightness_pct = 1
        self.char_brightness.set_value(brightness_pct)

    def _set_chars(self, char_values: dict[str, Any]) -> None:
        """Call the light services for a write from HomeKit."""
        _LOGGER.debug("%s: Set linked light chars: %s", self.entity_id, char_values)
        # The Home app also writes ConfiguredName, on pairing and on rename
        if CHAR_ON not in char_values and CHAR_BRIGHTNESS not in char_values:
            return
        params: dict[str, Any] = {ATTR_ENTITY_ID: self.entity_id}
        brightness_pct = char_values.get(CHAR_BRIGHTNESS)
        if (CHAR_ON in char_values and not char_values[CHAR_ON]) or brightness_pct == 0:
            self._accessory.async_call_service(
                LIGHT_DOMAIN, LightService.TURN_OFF, params, False
            )
            return
        if brightness_pct is not None:
            params[LightServiceArgument.BRIGHTNESS_PCT] = brightness_pct
        self._accessory.async_call_service(
            LIGHT_DOMAIN, LightService.TURN_ON, params, brightness_pct or True
        )


@callback
def async_create_linked_light(accessory: HomeAccessory) -> LinkedLight | None:
    """Add the Lightbulb service of the configured linked light, if any."""
    if not (entity_id := accessory.config.get(CONF_LINKED_LIGHT)):
        return None
    if (state := accessory.hass.states.get(entity_id)) is None:
        _LOGGER.warning(
            "%s: Linked light state missing: %s", accessory.entity_id, entity_id
        )
        return None
    return LinkedLight(accessory, entity_id, state)
