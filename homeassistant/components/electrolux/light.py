"""Light entity for Electrolux Integration."""

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Concatenate, override

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.hd_appliance import HDAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.feature_constants import (
    CAVITY_LIGHT,
    LIGHT_COLOR_TEMPERATURE,
    LIGHT_INTENSITY,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import convert_to_snake_case, round_to_valid_step_int

COLOR_RANGE = (0, 100)
COLOR_KELVIN_RANGE = (2200, 6500)

BRIGHTNESS_SCALE = (1, 100)


@dataclass(frozen=True, kw_only=True)
class ElectroluxLightBaseDescription[T: ApplianceData, **P = []](
    LightEntityDescription
):
    """Custom light description for Electrolux lights."""

    color_mode: ColorMode
    supported_color_modes: set[ColorMode]
    exists_fn: Callable[Concatenate[T, P], bool]
    min_color_fn: Callable[Concatenate[T, P], int | None] | None
    max_color_fn: Callable[Concatenate[T, P], int | None] | None
    color_fn: Callable[Concatenate[T, P], int | None] | None
    brightness_fn: Callable[Concatenate[T, P], int | None] | None
    is_on_fn: Callable[Concatenate[T, P], bool]
    turn_on_command_fn: Callable[
        Concatenate[T, int | None, int | None, P], list[dict[str, Any]]
    ]
    turn_off_command_fn: Callable[Concatenate[T, P], list[dict[str, Any]]]


@dataclass(frozen=True, kw_only=True)
class ElectroluxLightDescription[T: ApplianceData](
    ElectroluxLightBaseDescription[T, []]
):
    """Custom light description for Electrolux lights."""


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleLightDescription[T: ApplianceData](
    ElectroluxLightBaseDescription[T, [str]]
):
    """Custom light description for Electrolux appliance submodule lights."""


def hood_light_is_on_fn(appliance: HDAppliance) -> bool:
    """Determine if the hood light is on."""
    current_light_intensity = appliance.get_current_light_intensity()
    return current_light_intensity > 0


def hood_light_turn_on_command_fn(
    appliance: HDAppliance, brightness: int | None, color_temp: int | None
) -> list[dict[str, Any]]:
    """Generate the commands to turn on the hood light with the specified brightness and color."""
    commands = []

    is_on = hood_light_is_on_fn(appliance)
    current_light_intensity = appliance.get_current_light_intensity()
    light_intensity: float | None = None
    if brightness is not None:
        light_intensity = _map_from_brightness(brightness)
    elif not is_on:
        light_intensity = 70

    if light_intensity is not None:
        rounded_light_intensity = round_to_valid_step_int(
            light_intensity,
            appliance.get_min_light_intensity(),
            appliance.get_step_light_intensity(),
        )
        if rounded_light_intensity != current_light_intensity:
            commands.append(
                appliance.get_set_light_intensity_command(rounded_light_intensity)
            )

    current_color_temperature = appliance.get_current_light_color_temperature()
    color_temperature: float | None = _map_from_kelvin(color_temp)

    if color_temperature is not None:
        rounded_color_temperature = round_to_valid_step_int(
            color_temperature,
            appliance.get_min_light_color_temperature_range(),
            appliance.get_step_light_color_temperature_range(),
        )
        if rounded_color_temperature != current_color_temperature:
            commands.append(
                appliance.get_set_light_color_temperature_command(
                    rounded_color_temperature
                )
            )

    return commands


def hood_light_turn_off_command_fn(appliance: HDAppliance) -> list[dict[str, Any]]:
    """Generate the commands to turn off the hood light."""
    return [appliance.get_set_light_intensity_command(0)]


HOOD_LIGHTS: tuple[ElectroluxLightDescription[HDAppliance], ...] = (
    ElectroluxLightDescription(
        key="hood_light",
        translation_key="hood_light",
        supported_color_modes={ColorMode.COLOR_TEMP},
        color_mode=ColorMode.COLOR_TEMP,
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [LIGHT_INTENSITY, LIGHT_COLOR_TEMPERATURE]
        ),
        min_color_fn=lambda appliance: _map_to_kelvin(
            appliance.get_min_light_color_temperature_range()
        ),
        max_color_fn=lambda appliance: _map_to_kelvin(
            appliance.get_max_light_color_temperature_range()
        ),
        color_fn=lambda appliance: _map_to_kelvin(
            appliance.get_current_light_color_temperature()
        ),
        brightness_fn=lambda appliance: _map_to_brightness(
            appliance.get_current_light_intensity()
        ),
        is_on_fn=hood_light_is_on_fn,
        turn_on_command_fn=hood_light_turn_on_command_fn,
        turn_off_command_fn=hood_light_turn_off_command_fn,
    ),
)


def oven_cavity_light_turn_on_command_fn(
    appliance: OVAppliance, brightness: int | None, color_temp: int | None
) -> list[dict[str, Any]]:
    """Generate the commands to turn on the cavity light of an oven."""
    return [appliance.get_cavity_light_command(True)]


def oven_cavity_light_turn_off_command_fn(
    appliance: OVAppliance,
) -> list[dict[str, Any]]:
    """Generate the commands to turn off the cavity light of an oven."""
    return [appliance.get_cavity_light_command(False)]


OVEN_LIGHTS: tuple[ElectroluxLightDescription[OVAppliance], ...] = (
    ElectroluxLightDescription(
        key="cavity_light",
        translation_key="cavity_light",
        supported_color_modes={ColorMode.ONOFF},
        color_mode=ColorMode.ONOFF,
        exists_fn=lambda appliance: appliance.is_feature_supported(CAVITY_LIGHT),
        min_color_fn=None,
        max_color_fn=None,
        color_fn=None,
        brightness_fn=None,
        is_on_fn=lambda appliance: appliance.get_current_cavity_light(),
        turn_on_command_fn=oven_cavity_light_turn_on_command_fn,
        turn_off_command_fn=oven_cavity_light_turn_off_command_fn,
    ),
)


def structured_oven_cavity_light_turn_on_command_fn(
    appliance: SOAppliance, brightness: int | None, color_temp: int | None, cavity: str
) -> list[dict[str, Any]]:
    """Generate the commands to turn on the cavity light of an oven."""
    return [appliance.get_cavity_light_command(cavity, True)]


def structured_oven_cavity_light_turn_off_command_fn(
    appliance: SOAppliance, cavity: str
) -> list[dict[str, Any]]:
    """Generate the commands to turn off the cavity light of an oven."""
    return [appliance.get_cavity_light_command(cavity, False)]


STRUCTURED_OVEN_LIGHTS: tuple[ElectroluxSubmoduleLightDescription[SOAppliance], ...] = (
    ElectroluxSubmoduleLightDescription(
        key="cavity_light",
        translation_key="cavity_light",
        supported_color_modes={ColorMode.ONOFF},
        color_mode=ColorMode.ONOFF,
        exists_fn=lambda appliance, cavity: appliance.is_cavity_feature_supported(
            cavity, CAVITY_LIGHT
        ),
        min_color_fn=None,
        max_color_fn=None,
        color_fn=None,
        brightness_fn=None,
        is_on_fn=lambda appliance, cavity: appliance.get_current_cavity_cavity_light(
            cavity
        ),
        turn_on_command_fn=structured_oven_cavity_light_turn_on_command_fn,
        turn_off_command_fn=structured_oven_cavity_light_turn_off_command_fn,
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, HDAppliance):
        entities.extend(
            ElectroluxLight(appliance_data, coordinator, description)
            for description in HOOD_LIGHTS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, OVAppliance):
        entities.extend(
            ElectroluxLight(appliance_data, coordinator, description)
            for description in OVEN_LIGHTS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, SOAppliance):
        entities.extend(
            ElectroluxSubmoduleLight(appliance_data, coordinator, description, cavity)
            for cavity in appliance_data.get_supported_cavities()
            for description in STRUCTURED_OVEN_LIGHTS
            if description.exists_fn(appliance_data, cavity)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxBaseLight[T: ApplianceData](ElectroluxBaseEntity[T], LightEntity):
    """Representation of a generic light for Electrolux appliances."""

    @override
    def _update_attr_state(self) -> bool:
        state_changed = False

        if (new_color_temp := self._get_color()) != self._attr_color_temp_kelvin:
            self._attr_color_temp_kelvin = new_color_temp
            state_changed = True

        if (new_brightness := self._get_brightness()) != self._attr_brightness:
            self._attr_brightness = new_brightness
            state_changed = True

        if (new_is_on := self._is_on()) != self._attr_is_on:
            self._attr_is_on = new_is_on
            state_changed = True

        return state_changed

    @abstractmethod
    def _get_color(self) -> int | None: ...

    @abstractmethod
    def _get_brightness(self) -> int | None: ...

    @abstractmethod
    def _is_on(self) -> bool | None: ...

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness: int | None = kwargs.get(ATTR_BRIGHTNESS)
        color_temp: int | None = kwargs.get(ATTR_COLOR_TEMP_KELVIN)

        await self._execute_commands(self._get_turn_on_commands(brightness, color_temp))

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._execute_commands(self._get_turn_off_commands())

    @abstractmethod
    def _get_turn_on_commands(
        self, brightness: int | None, color_temp: int | None
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def _get_turn_off_commands(self) -> list[dict[str, Any]]: ...

    async def _execute_commands(self, commands: list[dict[str, Any]]) -> None:
        """Execute a list of commands for the appliance."""
        if commands:
            for command in commands:
                await self.coordinator.client.send_command(
                    self._appliance_data.appliance.applianceId, command
                )
            await self.coordinator.async_request_refresh()


class ElectroluxLight[T: ApplianceData](ElectroluxBaseLight[T]):
    """Representation of a generic light for Electrolux appliances."""

    entity_description: ElectroluxLightDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxLightDescription[T],
    ) -> None:
        """Initialize the light."""
        super().__init__(appliance_data, coordinator, description.key)
        self.entity_description = description

        self._attr_supported_color_modes = description.supported_color_modes
        self._attr_color_mode = description.color_mode
        if (
            description.min_color_fn is not None
            and (min_color := description.min_color_fn(appliance_data)) is not None
        ):
            self._attr_min_color_temp_kelvin = min_color
        if (
            description.max_color_fn is not None
            and (max_color := description.max_color_fn(appliance_data)) is not None
        ):
            self._attr_max_color_temp_kelvin = max_color

    @override
    def _get_color(self) -> int | None:
        description = self.entity_description
        if description.color_fn is None:
            return None

        color_temp = description.color_fn(self._appliance_data)
        if color_temp is None or not (0 <= color_temp <= 100):
            return None

        return color_temp

    @override
    def _get_brightness(self) -> int | None:
        description = self.entity_description
        if description.brightness_fn is None:
            return None

        brightness = description.brightness_fn(self._appliance_data)
        if brightness is None or not (0 < brightness <= 100):
            return None

        return brightness

    @override
    def _is_on(self) -> bool | None:
        description = self.entity_description
        if description.is_on_fn is None:
            return None

        return description.is_on_fn(self._appliance_data)

    @override
    def _get_turn_on_commands(
        self, brightness: int | None, color_temp: int | None
    ) -> list[dict[str, Any]]:
        description = self.entity_description
        if description.turn_on_command_fn is None:
            return []

        return description.turn_on_command_fn(
            self._appliance_data, brightness, color_temp
        )

    @override
    def _get_turn_off_commands(self) -> list[dict[str, Any]]:
        description = self.entity_description
        if description.turn_off_command_fn is None:
            return []

        return description.turn_off_command_fn(self._appliance_data)


class ElectroluxSubmoduleLight[T: ApplianceData](ElectroluxBaseLight[T]):
    """Representation of a generic light for Electrolux appliances."""

    entity_description: ElectroluxSubmoduleLightDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSubmoduleLightDescription[T],
        submodule: str,
    ) -> None:
        """Initialize the light."""
        entity_key = f"{convert_to_snake_case(submodule)}_{description.key}"
        translation_key = (
            f"{convert_to_snake_case(submodule)}_{description.translation_key}"
        )
        super().__init__(appliance_data, coordinator, entity_key)

        self._submodule = submodule
        self.entity_description = description
        self._attr_translation_key = translation_key

        self._attr_supported_color_modes = description.supported_color_modes
        self._attr_color_mode = description.color_mode
        if (
            description.min_color_fn is not None
            and (min_color := description.min_color_fn(appliance_data, submodule))
            is not None
        ):
            self._attr_min_color_temp_kelvin = min_color
        if (
            description.max_color_fn is not None
            and (max_color := description.max_color_fn(appliance_data, submodule))
            is not None
        ):
            self._attr_max_color_temp_kelvin = max_color

    @override
    def _get_color(self) -> int | None:
        description = self.entity_description
        if description.color_fn is None:
            return None

        color_temp = description.color_fn(self._appliance_data, self._submodule)
        if color_temp is None or not (0 <= color_temp <= 100):
            return None

        return color_temp

    @override
    def _get_brightness(self) -> int | None:
        description = self.entity_description
        if description.brightness_fn is None:
            return None

        brightness = description.brightness_fn(self._appliance_data, self._submodule)
        if brightness is None or not (0 < brightness <= 100):
            return None

        return brightness

    @override
    def _is_on(self) -> bool | None:
        description = self.entity_description
        if description.is_on_fn is None:
            return None

        return description.is_on_fn(self._appliance_data, self._submodule)

    @override
    def _get_turn_on_commands(
        self, brightness: int | None, color_temp: int | None
    ) -> list[dict[str, Any]]:
        description = self.entity_description
        if description.turn_on_command_fn is None:
            return []

        return description.turn_on_command_fn(
            self._appliance_data, brightness, color_temp, self._submodule
        )

    @override
    def _get_turn_off_commands(self) -> list[dict[str, Any]]:
        description = self.entity_description
        if description.turn_off_command_fn is None:
            return []

        return description.turn_off_command_fn(self._appliance_data, self._submodule)


def _map_to_kelvin(color_temp: int | None) -> int | None:
    if color_temp is None:
        return None
    kelvin_scale_size = COLOR_KELVIN_RANGE[1] - COLOR_KELVIN_RANGE[0]
    color_scale_size = COLOR_RANGE[1] - COLOR_RANGE[0]
    return round(
        COLOR_KELVIN_RANGE[0]
        + ((color_temp - COLOR_RANGE[0]) / color_scale_size) * kelvin_scale_size
    )


def _map_from_kelvin(kelvin_temp: int | None) -> float | None:
    if kelvin_temp is None:
        return None
    kelvin_scale_size = COLOR_KELVIN_RANGE[1] - COLOR_KELVIN_RANGE[0]
    color_scale_size = COLOR_RANGE[1] - COLOR_RANGE[0]
    return round(
        COLOR_RANGE[0]
        + ((kelvin_temp - COLOR_KELVIN_RANGE[0]) / kelvin_scale_size) * color_scale_size
    )


def _map_to_brightness(brightness: int | None) -> int | None:
    if brightness is None:
        return None
    return value_to_brightness(BRIGHTNESS_SCALE, brightness)


def _map_from_brightness(brightness: int | None) -> float | None:
    if brightness is None:
        return None
    return brightness_to_value(BRIGHTNESS_SCALE, brightness)
