"""Support for AirGradient select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from airgradient import AirGradientClient, Config
from airgradient.models import ConfigurationControl, TemperatureUnit

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AirGradientConfigCoordinator
from .entity import AirGradientEntity


@dataclass(frozen=True, kw_only=True)
class AirGradientSelectEntityDescription(SelectEntityDescription):
    """Describes AirGradient select entity."""

    value_fn: Callable[[Config], str]
    set_value_fn: Callable[[AirGradientClient, str], Awaitable[None]]


CONFIG_CONTROL_ENTITY = AirGradientSelectEntityDescription(
    key="configuration_control",
    translation_key="configuration_control",
    options=[x.value for x in ConfigurationControl],
    value_fn=lambda config: config.configuration_control,
    set_value_fn=lambda client, value: client.set_configuration_control(
        ConfigurationControl(value)
    ),
)

PROTECTED_SELECT_TYPES: tuple[AirGradientSelectEntityDescription, ...] = (
    AirGradientSelectEntityDescription(
        key="temperature_unit",
        translation_key="temperature_unit",
        options=[x.value for x in TemperatureUnit],
        value_fn=lambda config: config.temperature_unit,
        set_value_fn=lambda client, value: client.set_temperature_unit(
            TemperatureUnit(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AirGradient select entities based on a config entry."""

    coordinator: AirGradientConfigCoordinator = hass.data[DOMAIN][entry.entry_id][
        "config"
    ]

    entities = [AirGradientSelect(coordinator, CONFIG_CONTROL_ENTITY)]

    entities.extend(
        AirGradientProtectedSelect(coordinator, description)
        for description in PROTECTED_SELECT_TYPES
    )

    async_add_entities(entities)


class AirGradientSelect(AirGradientEntity, SelectEntity):
    """Defines an AirGradient select entity."""

    entity_description: AirGradientSelectEntityDescription
    coordinator: AirGradientConfigCoordinator

    def __init__(
        self,
        coordinator: AirGradientConfigCoordinator,
        description: AirGradientSelectEntityDescription,
    ) -> None:
        """Initialize AirGradient select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"

    @property
    def current_option(self) -> str:
        """Return the state of the select."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(self.coordinator.client, option)
        await self.coordinator.async_request_refresh()


class AirGradientProtectedSelect(AirGradientSelect):
    """Defines a protected AirGradient select entity."""

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if (
            self.coordinator.data.configuration_control
            is not ConfigurationControl.LOCAL
        ):
            raise ServiceValidationError("Configuration control is not set to local")
        await super().async_select_option(option)
