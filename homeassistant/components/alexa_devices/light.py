"""Support for lights."""

from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator, alexa_api_call
from .entity import AmazonEntity

PARALLEL_UPDATES = 1

BRIGHTNESS_SCALE = (1, 100)

LIGHT_DESCRIPTION = LightEntityDescription(key="light", name=None)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices lights based on a config entry."""

    coordinator = entry.runtime_data

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        known_devices.intersection_update(current_devices)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                AmazonLightEntity(coordinator, serial_num, LIGHT_DESCRIPTION)
                for serial_num in new_devices
                if coordinator.data[serial_num].primary_display_category == "LIGHT"
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AmazonLightEntity(AmazonEntity, LightEntity):
    """Light device."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
        description: LightEntityDescription,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, serial_num, description)
        features = self.device.features

        # Glow exposes its light shows as a single mode feature
        self._mode_instance: str | None = None
        self._effects: dict[str, str] = {}
        if mode := next(iter(features.get("mode", {}).items()), None):
            self._mode_instance, mode_feature = mode
            self._effects = {
                option["modeResources"]["friendlyName"]["value"]["text"]: option[
                    "value"
                ]
                for option in mode_feature.raw_configuration.get("modeOptions") or []
            }
        if self._effects:
            self._attr_supported_features = LightEntityFeature.EFFECT
            self._attr_effect_list = list(self._effects)

    def _sensor_value(
        self, feature_name: str, property_name: str, instance: str = ""
    ) -> Any:
        """Return the current value of a feature property, None if unknown."""
        if (
            (feature := self.device.features.get(feature_name, {}).get(instance))
            is None
            or (sensor_key := feature.sensor_keys.get(property_name)) is None
            or (sensor := self.coordinator.device_sensor(self._serial_num, sensor_key))
            is None
            or sensor.error
        ):
            return None
        return sensor.value

    async def _call(
        self,
        feature_name: str,
        operation_name: str,
        command_payload: dict[str, Any] | None = None,
        instance: str | None = None,
    ) -> None:
        """Invoke a feature operation on the light."""
        async with alexa_api_call(self.coordinator):
            await self.coordinator.api.call_feature_operation(
                self.device,
                feature_name,
                operation_name,
                command_payload=command_payload,
                instance=instance,
            )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        if (power := self._sensor_value("power", "powerState")) is None:
            return None
        return str(power) == "ON"

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if (brightness := self._sensor_value("brightness", "brightness")) is None:
            return None
        return value_to_brightness(BRIGHTNESS_SCALE, brightness)

    @property
    @override
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation of the light."""
        if (color := self._sensor_value("color", "color")) is None:
            return None
        return (color["hue"], color["saturation"] * 100)

    @property
    @override
    def effect(self) -> str | None:
        """Return the current effect of the light."""
        if (
            self._mode_instance is None
            or (mode := self._sensor_value("mode", "mode", self._mode_instance)) is None
        ):
            return None
        return next(
            (name for name, value in self._effects.items() if value == mode), None
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if not self.is_on:
            await self._call("power", "turnOn")
        if ATTR_BRIGHTNESS in kwargs:
            await self._call(
                "brightness",
                "setBrightness",
                {
                    "brightness": max(
                        1,
                        round(
                            brightness_to_value(
                                BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS]
                            )
                        ),
                    )
                },
            )
        if ATTR_HS_COLOR in kwargs:
            hue, saturation = kwargs[ATTR_HS_COLOR]
            await self._call(
                "color",
                "setColor",
                {
                    "color": {
                        "hue": hue,
                        "saturation": saturation / 100,
                        "brightness": 1.0,
                    }
                },
            )
        if ATTR_EFFECT in kwargs:
            await self._call(
                "mode",
                "setMode",
                {"mode": self._effects[kwargs[ATTR_EFFECT]]},
                self._mode_instance,
            )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._call("power", "turnOff")
