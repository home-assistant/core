"""Support for Qbus light."""

from typing import Any, override

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import (
    MultiColorRegime,
    MultiColorStateProperty,
    QbusMqttAnalogState,
    QbusMqttMultiColorState,
    StateType,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.components.mqtt import client as mqtt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, create_new_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _check_outputs() -> None:
        entities: list[QbusEntity] = [
            *create_new_entities(
                coordinator,
                added_outputs,
                lambda output: output.type == "analog",
                QbusLight,
            ),
            *create_new_entities(
                coordinator,
                added_outputs,
                lambda output: output.type == "multicolor",
                QbusMultiColor,
            ),
        ]

        async_add_entities(entities)

    _check_outputs()
    coordinator.async_add_listener(_check_outputs)


class QbusLight(QbusEntity, LightEntity):
    """Representation of a Qbus light entity."""

    _state_cls = QbusMqttAnalogState

    _attr_name = None
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize light entity."""

        super().__init__(mqtt_output)

        self._set_state(0)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        state = QbusMqttAnalogState(id=self._mqtt_output.id)

        if brightness is None:
            state.type = StateType.ACTION
            state.write_on_off(on=True)
        else:
            percentage = round(brightness_to_value((1, 100), brightness))

            state.type = StateType.STATE
            state.write_percentage(percentage)

        await self._async_publish_output_state(state)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        state = QbusMqttAnalogState(id=self._mqtt_output.id, type=StateType.ACTION)
        state.write_on_off(on=False)

        await self._async_publish_output_state(state)

    @override
    async def _handle_state_received(self, state: QbusMqttAnalogState) -> None:
        percentage = state.read_percentage()

        if percentage is not None:
            self._set_state(round(percentage))

    def _set_state(self, percentage: int) -> None:
        self._attr_is_on = percentage > 0
        self._attr_brightness = value_to_brightness((1, 100), percentage)


class QbusMultiColor(QbusEntity, LightEntity):
    """Representation of a Qbus multi-color entity."""

    _state_cls = QbusMqttMultiColorState

    _attr_name = None
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize light entity."""

        super().__init__(mqtt_output)

        self._attr_supported_features |= LightEntityFeature.TRANSITION

        preset_movie: dict = mqtt_output.properties.get(
            MultiColorStateProperty.PRESET_MOVIE, {}
        )
        effects: list[dict[str, Any]] = preset_movie.get("valueList", [])

        self._effect_name_to_value: dict[str, int] = {
            item["name"]: item["value"] for item in effects
        }
        self._effect_value_to_name: dict[int, str] = {
            item["value"]: item["name"] for item in effects
        }

        if effects:
            self._attr_supported_features |= LightEntityFeature.EFFECT
            self._attr_effect_list = [EFFECT_OFF]
            self._attr_effect_list.extend(effect["name"] for effect in effects)

        self._set_state(brightness=0)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        effect = kwargs.get(ATTR_EFFECT)

        state = QbusMqttMultiColorState(id=self._mqtt_output.id, type=StateType.STATE)

        if len(kwargs) == 0:
            state.write_on(True)

        if brightness is not None:
            percentage = round(brightness_to_value((1, 100), brightness))
            state.write_brightness(percentage)

        if hs_color is not None:
            state.write_hue(hs_color[0])
            state.write_saturation(hs_color[1])

        if effect == EFFECT_OFF:
            state.write_current_regime(MultiColorRegime.COLOR_WHEEL)
        elif effect is not None:
            movie = self._effect_name_to_value.get(effect)

            if movie is not None:
                state.write_preset_movie(movie)

        await self._async_publish_output_state(state)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        state = QbusMqttMultiColorState(id=self._mqtt_output.id, type=StateType.STATE)
        state.write_on(False)

        await self._async_publish_output_state(state)

    @override
    async def _handle_state_received(self, state: QbusMqttMultiColorState) -> None:
        if state.type == StateType.EVENT:
            # An event doesn't contain all properties, request full state
            await self._async_request_state()
            return

        effect: str | None = None
        hs: tuple[float, float] | None = None

        brightness = state.read_brightness()
        brightness = round(brightness) if brightness is not None else None

        regime = state.read_current_regime()

        if regime == MultiColorRegime.MOVIE_SELECT:
            movie = state.read_preset_movie()
            if movie is None:
                movie = -1
            effect = self._effect_value_to_name.get(movie, EFFECT_OFF)
        else:
            hue = state.read_hue()
            saturation = state.read_saturation()
            hs = (
                (hue, saturation)
                if hue is not None and saturation is not None
                else None
            )
            effect = EFFECT_OFF

        self._set_state(brightness=brightness, hs=hs, effect=effect)

    def _set_state(
        self,
        brightness: int | None = None,
        hs: tuple[float, float] | None = None,
        effect: str | None = None,
    ) -> None:
        if brightness is not None:
            self._attr_is_on = brightness > 0
            self._attr_brightness = value_to_brightness((1, 100), brightness)

        if hs is not None:
            self._attr_hs_color = hs

        self._attr_effect = effect

    async def _async_request_state(self) -> None:
        request = self._message_factory.create_state_request([self._mqtt_output.id])
        await mqtt.async_publish(self.hass, request.topic, request.payload)
