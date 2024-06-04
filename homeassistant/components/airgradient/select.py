"""Support for AirGradient select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from airgradient import AirGradientClient, Config
from airgradient.models import ConfigurationControl, TemperatureUnit

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AirGradientConfigCoordinator, AirGradientMeasurementCoordinator
from .entity import AirGradientEntity


@dataclass(frozen=True, kw_only=True)
class AirGradientSelectEntityDescription(SelectEntityDescription):
    """Describes AirGradient select entity."""

    value_fn: Callable[[Config], str | None]
    set_value_fn: Callable[[AirGradientClient, str], Awaitable[None]]
    requires_display: bool = False


CONFIG_CONTROL_ENTITY = AirGradientSelectEntityDescription(
    key="configuration_control",
    translation_key="configuration_control",
    options=[ConfigurationControl.CLOUD.value, ConfigurationControl.LOCAL.value],
    entity_category=EntityCategory.CONFIG,
    value_fn=lambda config: config.configuration_control
    if config.configuration_control is not ConfigurationControl.NOT_INITIALIZED
    else None,
    set_value_fn=lambda client, value: client.set_configuration_control(
        ConfigurationControl(value)
    ),
)

PROTECTED_SELECT_TYPES: tuple[AirGradientSelectEntityDescription, ...] = (
    AirGradientSelectEntityDescription(
        key="display_temperature_unit",
        translation_key="display_temperature_unit",
        options=[x.value for x in TemperatureUnit],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.temperature_unit,
        set_value_fn=lambda client, value: client.set_temperature_unit(
            TemperatureUnit(value)
        ),
        requires_display=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AirGradient select entities based on a config entry."""

    config_coordinator: AirGradientConfigCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]["config"]
    measurement_coordinator: AirGradientMeasurementCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]["measurement"]

    entities = [AirGradientSelect(config_coordinator, CONFIG_CONTROL_ENTITY)]

    entities.extend(
        AirGradientProtectedSelect(config_coordinator, description)
        for description in PROTECTED_SELECT_TYPES
        if (
            description.requires_display
            and measurement_coordinator.data.model.startswith("I")
        )
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
    def current_option(self) -> str | None:
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
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_local_configuration",
            )
        await super().async_select_option(option)
