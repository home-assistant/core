"""Switch platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from yoto_api import Capabilities, PlayerConfig, YotoPlayer, caps_for

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoConfigEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class YotoSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Yoto switch entity.

    ``value_fn`` reads the on/off state from the config.
    ``write_fn`` maps the desired state to ``set_player_config`` kwargs.
    ``supported_fn`` gates setup on the device's capabilities.
    """

    value_fn: Callable[[PlayerConfig], bool | None]
    write_fn: Callable[[bool], dict[str, Any]]
    supported_fn: Callable[[Capabilities], bool] = lambda caps: True


SWITCHES: tuple[YotoSwitchEntityDescription, ...] = (
    YotoSwitchEntityDescription(
        key="bluetooth_pairing",
        translation_key="bluetooth_pairing",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.bluetooth_enabled,
        write_fn=lambda on: {"bluetooth_enabled": on},
    ),
    YotoSwitchEntityDescription(
        key="max_headphone_volume",
        translation_key="max_headphone_volume",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.headphones_volume_limited,
        write_fn=lambda on: {"headphones_volume_limited": on},
    ),
    YotoSwitchEntityDescription(
        key="day_mode_auto_brightness",
        translation_key="day_mode_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.day_display_brightness_auto,
        write_fn=lambda on: {"day_display_brightness_auto": on},
        supported_fn=lambda caps: caps.has_light_sensor,
    ),
    YotoSwitchEntityDescription(
        key="night_mode_auto_brightness",
        translation_key="night_mode_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.night_display_brightness_auto,
        write_fn=lambda on: {"night_display_brightness_auto": on},
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
    known_players: set[str] = set()

    @callback
    def _add_players() -> None:
        current = set(coordinator.data)
        new_players = current - known_players
        known_players.clear()
        known_players.update(current)
        if new_players:
            async_add_entities(
                YotoSwitch(coordinator, coordinator.data[player_id], description)
                for player_id in new_players
                for description in SWITCHES
                if description.supported_fn(
                    caps_for(coordinator.data[player_id].device)
                )
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_players))
    _add_players()


class YotoSwitch(YotoConfigEntity, SwitchEntity):
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
    @override
    def is_on(self) -> bool | None:
        """Return whether the setting is enabled."""
        return self.entity_description.value_fn(self.player.info.config)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting."""
        await self._async_set_config(**self.entity_description.write_fn(True))

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting."""
        await self._async_set_config(**self.entity_description.write_fn(False))
