"""Light platform for the OSRAM infrared integration."""

import logging
from typing import Any, Final, override

from infrared_protocols.codes.osram.light import OSRAM_ADDRESS, OsramLightCode
from infrared_protocols.commands.nec import NECCommand

from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    async_subscribe_receiver,
)
from homeassistant.components.light import (
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_IR_EMITTER_ENTITY_ID, CONF_IR_RECEIVER_ENTITY_ID
from .entity import OsramIrEmitterEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Use the dedicated white command for colors with low saturation.
WHITE_SATURATION_THRESHOLD = 45.0

# The physical remote exposes 15 discrete color presets.
HUE_TO_CODE: Final[dict[int, OsramLightCode]] = {
    0: OsramLightCode.HUE_000,
    15: OsramLightCode.HUE_015,
    30: OsramLightCode.HUE_030,
    45: OsramLightCode.HUE_045,
    60: OsramLightCode.HUE_060,
    120: OsramLightCode.HUE_120,
    135: OsramLightCode.HUE_135,
    150: OsramLightCode.HUE_150,
    165: OsramLightCode.HUE_165,
    180: OsramLightCode.HUE_180,
    240: OsramLightCode.HUE_240,
    255: OsramLightCode.HUE_255,
    270: OsramLightCode.HUE_270,
    285: OsramLightCode.HUE_285,
    300: OsramLightCode.HUE_300,
}

SUPPORTED_HUES: Final[tuple[int, ...]] = (*HUE_TO_CODE, 360)

CODE_TO_HUE: Final[dict[OsramLightCode, int]] = {
    code: hue for hue, code in HUE_TO_CODE.items()
}

EFFECT_TO_CODE: Final[dict[str, OsramLightCode]] = {
    "flash": OsramLightCode.FLASH,
    "strobe": OsramLightCode.STROBE,
    "smooth": OsramLightCode.SMOOTH,
}

CODE_TO_EFFECT: Final[dict[OsramLightCode, str]] = {
    code: effect for effect, code in EFFECT_TO_CODE.items()
}

EFFECT_LIST: Final[list[str]] = [
    EFFECT_OFF,
    *EFFECT_TO_CODE,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an OSRAM infrared light from a config entry."""
    if not (emitter_entity_id := entry.data.get(CONF_IR_EMITTER_ENTITY_ID)):
        return

    async_add_entities(
        [
            OsramIrLight(
                entry,
                emitter_entity_id,
                entry.data.get(CONF_IR_RECEIVER_ENTITY_ID),
            )
        ]
    )


class OsramIrLight(OsramIrEmitterEntity, LightEntity):
    """Representation of an OSRAM infrared light."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.HS
    _attr_effect_list = EFFECT_LIST
    _attr_hs_color = (0.0, 0.0)
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(
        self,
        entry: ConfigEntry,
        emitter_entity_id: str,
        receiver_entity_id: str | None,
    ) -> None:
        """Initialize an OSRAM infrared light."""
        super().__init__(
            entry,
            emitter_entity_id,
            unique_id_suffix="light",
        )

        self._infrared_receiver_entity_id = receiver_entity_id
        self._remove_signal_subscription: CALLBACK_TYPE | None = None

        # The bulb does not provide direct state feedback. Track an assumed
        # state based on commands sent by this entity or received from a
        # configured infrared receiver.
        self._attr_is_on = False
        self._attr_effect = EFFECT_OFF
        self._last_static_color_code = OsramLightCode.WHITE
        self._last_static_hs_color = (0.0, 0.0)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to signals from the optional infrared receiver."""
        await super().async_added_to_hass()

        if self._infrared_receiver_entity_id is None:
            return

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._infrared_receiver_entity_id],
                self._async_receiver_state_changed,
            )
        )
        self._async_update_receiver_subscription()
        self.async_on_remove(self._async_unsubscribe_receiver)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light and apply optional effect and  color."""
        if not self._attr_is_on:
            await self._async_send_code(
                OsramLightCode.ON,
                repeat_count=5,
            )

        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            await self._async_set_effect(effect)
        elif (hs_color := kwargs.get(ATTR_HS_COLOR)) is not None:
            await self._async_set_hs_color(hs_color)

        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_send_code(
            OsramLightCode.OFF,
            repeat_count=5,
        )

        self._update_off_state()
        self.async_write_ha_state()

    async def _async_set_hs_color(
        self,
        hs_color: tuple[float, float],
    ) -> None:
        """Set the nearest supported static color preset."""
        hue, saturation = hs_color

        if saturation <= WHITE_SATURATION_THRESHOLD:
            code = OsramLightCode.WHITE
            reported_hs_color = (0.0, 0.0)
        else:
            snapped_hue = _snap_hue(hue)
            code = HUE_TO_CODE[snapped_hue]
            reported_hs_color = (float(snapped_hue), 100.0)

        await self._async_send_code(
            code,
            repeat_count=5,
        )

        self._update_static_color_state(code, reported_hs_color)

    async def _async_set_effect(self, effect: str) -> None:
        """Start or stop a native OSRAM effect."""
        if effect == EFFECT_OFF:
            await self._async_send_code(
                self._last_static_color_code,
                repeat_count=5,
            )

            self._update_static_color_state(
                self._last_static_color_code,
                self._last_static_hs_color,
            )
            return

        try:
            code = EFFECT_TO_CODE[effect]
        except KeyError as err:
            raise HomeAssistantError(
                f"Unsupported OSRAM infrared effect: {effect}"
            ) from err

        await self._async_send_code(code)
        self._update_effect_state(effect)

    @callback
    def _async_receiver_state_changed(
        self,
        event: Event[EventStateChangedData],
    ) -> None:
        """Update the receiver subscription after availability changes."""
        self._async_update_receiver_subscription()

    @callback
    def _async_update_receiver_subscription(self) -> None:
        """Subscribe or unsubscribe when the receiver becomes available."""
        if self._infrared_receiver_entity_id is None:
            return

        receiver_state = self.hass.states.get(self._infrared_receiver_entity_id)

        if receiver_state is None or receiver_state.state == STATE_UNAVAILABLE:
            self._async_unsubscribe_receiver()
            return

        if self._remove_signal_subscription is not None:
            return

        try:
            self._remove_signal_subscription = async_subscribe_receiver(
                self.hass,
                self._infrared_receiver_entity_id,
                self._handle_signal,
            )
        except HomeAssistantError:
            _LOGGER.debug(
                "Unable to subscribe to OSRAM infrared receiver %s",
                self._infrared_receiver_entity_id,
                exc_info=True,
            )
            return

        _LOGGER.debug(
            "Subscribed to OSRAM infrared receiver %s",
            self._infrared_receiver_entity_id,
        )

    @callback
    def _async_unsubscribe_receiver(self) -> None:
        """Unsubscribe from the configured infrared receiver."""
        if self._remove_signal_subscription is None:
            return

        self._remove_signal_subscription()
        self._remove_signal_subscription = None

    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update the assumed light state after receiving an OSRAM command."""
        nec_command = NECCommand.from_raw_timings(signal.timings)

        if nec_command is None or nec_command.address != OSRAM_ADDRESS:
            return

        try:
            code = OsramLightCode(nec_command.command)
        except ValueError:
            _LOGGER.debug(
                "Ignoring unknown OSRAM infrared command: 0x%02X",
                nec_command.command,
            )
            return

        _LOGGER.debug(
            "Received OSRAM infrared command: %s (0x%02X)",
            code.name,
            nec_command.command,
        )

        self._apply_received_code(code)
        self.async_write_ha_state()

    @callback
    def _apply_received_code(self, code: OsramLightCode) -> None:
        """Apply a received infrared command without transmitting anything."""
        if code is OsramLightCode.OFF:
            self._update_off_state()
            return

        # Every other recognized command requires the bulb to be powered on.
        self._attr_is_on = True

        if code is OsramLightCode.ON:
            return

        if code is OsramLightCode.WHITE:
            self._update_static_color_state(
                OsramLightCode.WHITE,
                (0.0, 0.0),
            )
            return

        if (hue := CODE_TO_HUE.get(code)) is not None:
            self._update_static_color_state(
                code,
                (float(hue), 100.0),
            )
            return

        if (effect := CODE_TO_EFFECT.get(code)) is not None:
            self._update_effect_state(effect)
            return

        if code is OsramLightCode.MODE:
            # MODE changes a bulb-specific mode but does not map reliably to a
            # Home Assistant light effect.
            return

    @callback
    def _update_off_state(self) -> None:
        """Update the local state after an off command."""
        self._attr_is_on = False
        self._attr_effect = EFFECT_OFF
        self._attr_color_mode = ColorMode.HS

    @callback
    def _update_static_color_state(
        self,
        code: OsramLightCode,
        hs_color: tuple[float, float],
    ) -> None:
        """Update the local state after selecting a static color."""
        self._attr_is_on = True
        self._attr_effect = EFFECT_OFF
        self._attr_color_mode = ColorMode.HS
        self._attr_hs_color = hs_color
        self._last_static_color_code = code
        self._last_static_hs_color = hs_color

    @callback
    def _update_effect_state(self, effect: str) -> None:
        """Update the local state after selecting an effect."""
        self._attr_is_on = True
        self._attr_effect = effect


def _snap_hue(hue: float) -> int:
    """Snap an arbitrary hue to the nearest physical remote preset."""
    normalized_hue = hue % 360

    # 360° is included as an alias for 0° to handle the wrap-around at red.
    return (
        min(
            SUPPORTED_HUES,
            key=lambda supported_hue: abs(normalized_hue - supported_hue),
        )
        % 360
    )
