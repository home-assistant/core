"""Switch platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yoto_api import Capabilities, PlayerConfig, YotoPlayer, caps_for

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 1

# When auto brightness is switched off the API needs an explicit brightness
# value to replace the "auto" sentinel; fall back to full brightness if the
# config never held a manual value.
DEFAULT_DISPLAY_BRIGHTNESS = 100


def _invert(value: bool | None) -> bool | None:
    """Invert an optional boolean, keeping None as None."""
    return None if value is None else not value


@dataclass(frozen=True, kw_only=True)
class YotoSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Yoto switch entity.

    The turn_on/turn_off callables return the ``set_player_config`` kwargs
    that put the player in the requested state. ``supported_fn`` gates
    entity creation on the player model's capabilities.
    """

    is_on_fn: Callable[[PlayerConfig], bool | None]
    turn_on_fn: Callable[[PlayerConfig], dict[str, Any]]
    turn_off_fn: Callable[[PlayerConfig], dict[str, Any]]
    supported_fn: Callable[[Capabilities], bool] = lambda caps: True


SWITCHES: tuple[YotoSwitchEntityDescription, ...] = (
    YotoSwitchEntityDescription(
        key="bluetooth",
        translation_key="bluetooth",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: config.bluetooth_enabled,
        turn_on_fn=lambda config: {"bluetooth_enabled": True},
        turn_off_fn=lambda config: {"bluetooth_enabled": False},
    ),
    YotoSwitchEntityDescription(
        key="bluetooth_headphones",
        translation_key="bluetooth_headphones",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: config.bt_headphones_enabled,
        turn_on_fn=lambda config: {"bt_headphones_enabled": True},
        turn_off_fn=lambda config: {"bt_headphones_enabled": False},
    ),
    YotoSwitchEntityDescription(
        key="headphones_volume_limit",
        translation_key="headphones_volume_limit",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: config.headphones_volume_limited,
        turn_on_fn=lambda config: {"headphones_volume_limited": True},
        turn_off_fn=lambda config: {"headphones_volume_limited": False},
    ),
    YotoSwitchEntityDescription(
        key="repeat_all",
        translation_key="repeat_all",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: config.repeat_all,
        turn_on_fn=lambda config: {"repeat_all": True},
        turn_off_fn=lambda config: {"repeat_all": False},
    ),
    # The Yoto API stores "sounds off"; expose it as a "sounds on" switch to
    # match the system sounds toggle in the Yoto app.
    YotoSwitchEntityDescription(
        key="day_sounds",
        translation_key="day_sounds",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: _invert(config.day_sounds_off),
        turn_on_fn=lambda config: {"day_sounds_off": False},
        turn_off_fn=lambda config: {"day_sounds_off": True},
    ),
    YotoSwitchEntityDescription(
        key="night_sounds",
        translation_key="night_sounds",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: _invert(config.night_sounds_off),
        turn_on_fn=lambda config: {"night_sounds_off": False},
        turn_off_fn=lambda config: {"night_sounds_off": True},
    ),
    YotoSwitchEntityDescription(
        key="pause_volume_down",
        translation_key="pause_volume_down",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: config.pause_volume_down,
        turn_on_fn=lambda config: {"pause_volume_down": True},
        turn_off_fn=lambda config: {"pause_volume_down": False},
    ),
    YotoSwitchEntityDescription(
        key="pause_power_button",
        translation_key="pause_power_button",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: config.pause_power_button,
        turn_on_fn=lambda config: {"pause_power_button": True},
        turn_off_fn=lambda config: {"pause_power_button": False},
    ),
    # Automatic display brightness needs the ambient light sensor, which
    # only some player models have.
    YotoSwitchEntityDescription(
        key="day_auto_brightness",
        translation_key="day_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: config.day_display_brightness_auto,
        turn_on_fn=lambda config: {"day_display_brightness_auto": True},
        turn_off_fn=lambda config: {
            "day_display_brightness": config.day_display_brightness
            or DEFAULT_DISPLAY_BRIGHTNESS
        },
        supported_fn=lambda caps: caps.has_light_sensor,
    ),
    YotoSwitchEntityDescription(
        key="night_auto_brightness",
        translation_key="night_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda config: config.night_display_brightness_auto,
        turn_on_fn=lambda config: {"night_display_brightness_auto": True},
        turn_off_fn=lambda config: {
            "night_display_brightness": config.night_display_brightness
            or DEFAULT_DISPLAY_BRIGHTNESS
        },
        supported_fn=lambda caps: caps.has_light_sensor,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto switch platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        YotoSwitch(coordinator, player, description)
        for player in coordinator.client.players.values()
        for description in SWITCHES
        if description.supported_fn(caps_for(player.device))
    )


class YotoSwitch(YotoEntity, SwitchEntity):
    """Representation of a Yoto player config switch."""

    entity_description: YotoSwitchEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
        description: YotoSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, player)
        self.entity_description = description
        self._attr_unique_id = f"{player.id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the switch state."""
        return self.entity_description.is_on_fn(self.player.info.config)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_config(
            **self.entity_description.turn_on_fn(self.player.info.config)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_config(
            **self.entity_description.turn_off_fn(self.player.info.config)
        )
