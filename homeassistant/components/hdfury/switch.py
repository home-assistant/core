"""Switch platform for HDFury Integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from hdfury import HDFuryAPI, HDFuryError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import HDFuryConfigEntry
from .entity import HDFuryEntity

PARALLEL_UPDATES = 1


@dataclass(kw_only=True, frozen=True)
class HDFurySwitchEntityDescription(SwitchEntityDescription):
    """Description for HDFury switch entities."""

    set_value_fn: Callable[[HDFuryAPI, str], Awaitable[None]]


SWITCHES: tuple[HDFurySwitchEntityDescription, ...] = (
    HDFurySwitchEntityDescription(
        key="autosw",
        translation_key="autosw",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_auto_switch_inputs(value),
    ),
    HDFurySwitchEntityDescription(
        key="cec",
        translation_key="cec",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_cec(value),
    ),
    HDFurySwitchEntityDescription(
        key="cec0en",
        translation_key="cec0en",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_cec_rx0(value),
    ),
    HDFurySwitchEntityDescription(
        key="cec1en",
        translation_key="cec1en",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_cec_rx1(value),
    ),
    HDFurySwitchEntityDescription(
        key="cec2en",
        translation_key="cec2en",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_cec_rx2(value),
    ),
    HDFurySwitchEntityDescription(
        key="cec3en",
        translation_key="cec3en",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_cec_rx3(value),
    ),
    HDFurySwitchEntityDescription(
        key="htpcmode0",
        translation_key="htpcmode0",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_htpc_mode_rx0(value),
    ),
    HDFurySwitchEntityDescription(
        key="htpcmode1",
        translation_key="htpcmode1",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_htpc_mode_rx1(value),
    ),
    HDFurySwitchEntityDescription(
        key="htpcmode2",
        translation_key="htpcmode2",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_htpc_mode_rx2(value),
    ),
    HDFurySwitchEntityDescription(
        key="htpcmode3",
        translation_key="htpcmode3",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_htpc_mode_rx3(value),
    ),
    HDFurySwitchEntityDescription(
        key="mutetx0",
        translation_key="mutetx0",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_mute_tx0_audio(value),
    ),
    HDFurySwitchEntityDescription(
        key="mutetx1",
        translation_key="mutetx1",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_mute_tx1_audio(value),
    ),
    HDFurySwitchEntityDescription(
        key="oled",
        translation_key="oled",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_oled(value),
    ),
    HDFurySwitchEntityDescription(
        key="iractive",
        translation_key="iractive",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_ir_active(value),
    ),
    HDFurySwitchEntityDescription(
        key="relay",
        translation_key="relay",
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_relay(value),
    ),
    HDFurySwitchEntityDescription(
        key="tx0plus5",
        translation_key="tx0plus5",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_tx0_force_5v(value),
    ),
    HDFurySwitchEntityDescription(
        key="tx1plus5",
        translation_key="tx1plus5",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        set_value_fn=lambda client, value: client.set_tx1_force_5v(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HDFuryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches using the platform schema."""

    coordinator = entry.runtime_data

    async_add_entities(
        HDFurySwitch(coordinator, description)
        for description in SWITCHES
        if description.key in coordinator.data.config
    )


class HDFurySwitch(HDFuryEntity, SwitchEntity):
    """Base HDFury Switch Class."""

    entity_description: HDFurySwitchEntityDescription

    @property
    def is_on(self) -> bool:
        """Set Switch State."""

        return self.coordinator.data.config.get(self.entity_description.key) == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Handle Switch On Event."""

        try:
            await self.entity_description.set_value_fn(self.coordinator.client, "on")
        except HDFuryError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Handle Switch Off Event."""

        try:
            await self.entity_description.set_value_fn(self.coordinator.client, "off")
        except HDFuryError as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from error

        await self.coordinator.async_request_refresh()
