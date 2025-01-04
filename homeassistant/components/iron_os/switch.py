"""Switch platform for IronOS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pynecil import CharSetting, SettingsDataResponse

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IronOSConfigEntry
from .coordinator import IronOSCoordinators
from .entity import IronOSBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IronOSSwitchEntityDescription(SwitchEntityDescription):
    """Describes IronOS switch entity."""

    is_on_fn: Callable[[SettingsDataResponse], bool | None]
    characteristic: CharSetting


class IronOSSwitch(StrEnum):
    """Switch controls for IronOS device."""

    ANIMATION_LOOP = "animation_loop"
    COOLING_TEMP_BLINK = "cooling_temp_blink"
    IDLE_SCREEN_DETAILS = "idle_screen_details"
    SOLDER_SCREEN_DETAILS = "solder_screen_details"
    INVERT_BUTTONS = "invert_buttons"
    DISPLAY_INVERT = "display_invert"
    CALIBRATE_CJC = "calibrate_cjc"
    USB_PD_MODE = "usb_pd_mode"


SWITCH_DESCRIPTIONS: tuple[IronOSSwitchEntityDescription, ...] = (
    IronOSSwitchEntityDescription(
        key=IronOSSwitch.ANIMATION_LOOP,
        translation_key=IronOSSwitch.ANIMATION_LOOP,
        characteristic=CharSetting.ANIMATION_LOOP,
        is_on_fn=lambda x: x.get("animation_loop"),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSSwitchEntityDescription(
        key=IronOSSwitch.COOLING_TEMP_BLINK,
        translation_key=IronOSSwitch.COOLING_TEMP_BLINK,
        characteristic=CharSetting.COOLING_TEMP_BLINK,
        is_on_fn=lambda x: x.get("cooling_temp_blink"),
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSSwitchEntityDescription(
        key=IronOSSwitch.IDLE_SCREEN_DETAILS,
        translation_key=IronOSSwitch.IDLE_SCREEN_DETAILS,
        characteristic=CharSetting.IDLE_SCREEN_DETAILS,
        is_on_fn=lambda x: x.get("idle_screen_details"),
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSSwitchEntityDescription(
        key=IronOSSwitch.SOLDER_SCREEN_DETAILS,
        translation_key=IronOSSwitch.SOLDER_SCREEN_DETAILS,
        characteristic=CharSetting.SOLDER_SCREEN_DETAILS,
        is_on_fn=lambda x: x.get("solder_screen_details"),
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSSwitchEntityDescription(
        key=IronOSSwitch.INVERT_BUTTONS,
        translation_key=IronOSSwitch.INVERT_BUTTONS,
        characteristic=CharSetting.INVERT_BUTTONS,
        is_on_fn=lambda x: x.get("invert_buttons"),
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSSwitchEntityDescription(
        key=IronOSSwitch.DISPLAY_INVERT,
        translation_key=IronOSSwitch.DISPLAY_INVERT,
        characteristic=CharSetting.DISPLAY_INVERT,
        is_on_fn=lambda x: x.get("display_invert"),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSSwitchEntityDescription(
        key=IronOSSwitch.CALIBRATE_CJC,
        translation_key=IronOSSwitch.CALIBRATE_CJC,
        characteristic=CharSetting.CALIBRATE_CJC,
        is_on_fn=lambda x: x.get("calibrate_cjc"),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSSwitchEntityDescription(
        key=IronOSSwitch.USB_PD_MODE,
        translation_key=IronOSSwitch.USB_PD_MODE,
        characteristic=CharSetting.USB_PD_MODE,
        is_on_fn=lambda x: x.get("usb_pd_mode"),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IronOSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""

    coordinators = entry.runtime_data

    async_add_entities(
        IronOSSwitchEntity(coordinators, description)
        for description in SWITCH_DESCRIPTIONS
    )


class IronOSSwitchEntity(IronOSBaseEntity, SwitchEntity):
    """Representation of a IronOS Switch."""

    entity_description: IronOSSwitchEntityDescription

    def __init__(
        self,
        coordinators: IronOSCoordinators,
        entity_description: IronOSSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinators.live_data, entity_description)

        self.settings = coordinators.settings

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.is_on_fn(
            self.settings.data,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.settings.write(self.entity_description.characteristic, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.settings.write(self.entity_description.characteristic, False)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        await super().async_added_to_hass()
        self.async_on_remove(
            self.settings.async_add_listener(
                self._handle_coordinator_update, self.entity_description.characteristic
            )
        )
        await self.settings.async_request_refresh()
