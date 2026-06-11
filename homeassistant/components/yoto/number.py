"""Number platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass

from yoto_api import PlayerConfig, YotoPlayer

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class YotoNumberEntityDescription(NumberEntityDescription):
    """Describes a Yoto number entity.

    ``config_field`` is the ``set_player_config`` kwarg written on change.
    """

    value_fn: Callable[[PlayerConfig], int | None]
    config_field: str
    available_fn: Callable[[PlayerConfig], bool] = lambda config: True


NUMBERS: tuple[YotoNumberEntityDescription, ...] = (
    # Max volume limits use the player's 16 hardware volume steps, not a
    # percentage — the same scale the firmware reports for playback volume.
    YotoNumberEntityDescription(
        key="day_max_volume_limit",
        translation_key="day_max_volume_limit",
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.day_max_volume_limit,
        config_field="day_max_volume_limit",
    ),
    YotoNumberEntityDescription(
        key="night_max_volume_limit",
        translation_key="night_max_volume_limit",
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.night_max_volume_limit,
        config_field="night_max_volume_limit",
    ),
    # Manual day/night display brightness only applies while automatic
    # brightness is off; the sliders go unavailable while auto is active
    # (turn the matching auto-brightness switch off to use them).
    YotoNumberEntityDescription(
        key="day_display_brightness",
        translation_key="day_display_brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.day_display_brightness,
        config_field="day_display_brightness",
        available_fn=lambda config: not config.day_display_brightness_auto,
    ),
    YotoNumberEntityDescription(
        key="night_display_brightness",
        translation_key="night_display_brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.night_display_brightness,
        config_field="night_display_brightness",
        available_fn=lambda config: not config.night_display_brightness_auto,
    ),
    YotoNumberEntityDescription(
        key="display_dim_brightness",
        translation_key="display_dim_brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.display_dim_brightness,
        config_field="display_dim_brightness",
    ),
    YotoNumberEntityDescription(
        key="shutdown_timeout",
        translation_key="shutdown_timeout",
        device_class=NumberDeviceClass.DURATION,
        native_min_value=0,
        native_max_value=14400,
        native_step=60,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.shutdown_timeout,
        config_field="shutdown_timeout",
    ),
    YotoNumberEntityDescription(
        key="display_dim_timeout",
        translation_key="display_dim_timeout",
        device_class=NumberDeviceClass.DURATION,
        native_min_value=0,
        native_max_value=3600,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.display_dim_timeout,
        config_field="display_dim_timeout",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto number platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        YotoNumber(coordinator, player, description)
        for player in coordinator.client.players.values()
        for description in NUMBERS
    )


class YotoNumber(YotoEntity, NumberEntity):
    """Representation of a Yoto player config number."""

    entity_description: YotoNumberEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
        description: YotoNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, player)
        self.entity_description = description
        self._attr_unique_id = f"{player.id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(
            self.player.info.config
        )

    @property
    def native_value(self) -> int | None:
        """Return the number value."""
        return self.entity_description.value_fn(self.player.info.config)

    async def async_set_native_value(self, value: float) -> None:
        """Update the config value."""
        await self._async_set_config(
            **{self.entity_description.config_field: int(value)}
        )
