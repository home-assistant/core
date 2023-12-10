"""Switch platform for La Marzocco espresso machines."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lmcloud.const import LaMarzoccoModel

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription
from .lm_client import LaMarzoccoClient

ATTR_MAP_MAIN_GS3_AV = [
    "dose_k1",
    "dose_k2",
    "dose_k3",
    "dose_k4",
    "dose_k5",
]

ATTR_MAP_AUTO_ON_OFF = [
    "mon_auto",
    "mon_on_time",
    "mon_off_time",
    "tue_auto",
    "tue_on_time",
    "tue_off_time",
    "wed_auto",
    "wed_on_time",
    "wed_off_time",
    "thu_auto",
    "thu_on_time",
    "thu_off_time",
    "fri_auto",
    "fri_on_time",
    "fri_off_time",
    "sat_auto",
    "sat_on_time",
    "sat_off_time",
    "sun_auto",
    "sun_on_time",
    "sun_off_time",
]

ATTR_MAP_PREBREW_GS3_AV = [
    "prebrewing_ton_k1",
    "prebrewing_toff_k1",
    "prebrewing_ton_k2",
    "prebrewing_toff_k2",
    "prebrewing_ton_k3",
    "prebrewing_toff_k3",
    "prebrewing_ton_k4",
    "prebrewing_toff_k4",
]

ATTR_MAP_PREBREW_LM = [
    "prebrewing_ton_k1",
    "prebrewing_toff_k1",
]

ATTR_MAP_PREINFUSION_LM = [
    "preinfusion_k1",
]
ATTR_MAP_PREINFUSION_GS3_AV = [
    "preinfusion_k1",
    "preinfusion_k2",
    "preinfusion_k3",
    "preinfusion_k4",
]


@dataclass
class LaMarzoccoSwitchEntityDescriptionMixin:
    """Description of an La Marzocco Switch."""

    control_fn: Callable[[LaMarzoccoClient, bool], Coroutine[Any, Any, bool]]
    is_on_fn: Callable[[LaMarzoccoClient], bool]


@dataclass
class LaMarzoccoSwitchEntityDescription(
    SwitchEntityDescription,
    LaMarzoccoEntityDescription,
    LaMarzoccoSwitchEntityDescriptionMixin,
):
    """Description of an La Marzocco Switch."""


ENTITIES: tuple[LaMarzoccoSwitchEntityDescription, ...] = (
    LaMarzoccoSwitchEntityDescription(
        key="main",
        translation_key="main",
        icon="mdi:power",
        control_fn=lambda client, state: client.set_power(state),
        is_on_fn=lambda client: client.current_status["power"],
        extra_attributes={
            LaMarzoccoModel.GS3_AV: ATTR_MAP_MAIN_GS3_AV,
            LaMarzoccoModel.GS3_MP: None,
            LaMarzoccoModel.LINEA_MINI: None,
            LaMarzoccoModel.LINEA_MICRA: None,
        },
    ),
    LaMarzoccoSwitchEntityDescription(
        key="auto_on_off",
        translation_key="auto_on_off",
        icon="mdi:alarm",
        control_fn=lambda client, state: client.set_auto_on_off_global(state),
        is_on_fn=lambda client: client.current_status["global_auto"] == "Enabled",
        entity_category=EntityCategory.CONFIG,
        extra_attributes={
            LaMarzoccoModel.GS3_AV: ATTR_MAP_AUTO_ON_OFF,
            LaMarzoccoModel.GS3_MP: ATTR_MAP_AUTO_ON_OFF,
            LaMarzoccoModel.LINEA_MINI: ATTR_MAP_AUTO_ON_OFF,
            LaMarzoccoModel.LINEA_MICRA: ATTR_MAP_AUTO_ON_OFF,
        },
    ),
    LaMarzoccoSwitchEntityDescription(
        key="prebrew",
        translation_key="prebrew",
        icon="mdi:water",
        control_fn=lambda client, state: client.set_prebrew(state),
        is_on_fn=lambda client: client.current_status["enable_prebrewing"],
        entity_category=EntityCategory.CONFIG,
        extra_attributes={
            LaMarzoccoModel.GS3_AV: ATTR_MAP_PREBREW_GS3_AV,
            LaMarzoccoModel.LINEA_MINI: ATTR_MAP_PREBREW_LM,
            LaMarzoccoModel.LINEA_MICRA: ATTR_MAP_PREBREW_LM,
        },
    ),
    LaMarzoccoSwitchEntityDescription(
        key="preinfusion",
        translation_key="preinfusion",
        icon="mdi:water",
        control_fn=lambda client, state: client.set_preinfusion(state),
        is_on_fn=lambda client: client.current_status["enable_preinfusion"],
        entity_category=EntityCategory.CONFIG,
        extra_attributes={
            LaMarzoccoModel.GS3_AV: ATTR_MAP_PREINFUSION_GS3_AV,
            LaMarzoccoModel.LINEA_MINI: ATTR_MAP_PREINFUSION_LM,
            LaMarzoccoModel.LINEA_MICRA: ATTR_MAP_PREINFUSION_LM,
        },
    ),
    LaMarzoccoSwitchEntityDescription(
        key="steam_boiler_enable",
        translation_key="steam_boiler_enable",
        icon="mdi:water-boiler",
        control_fn=lambda client, state: client.set_steam_boiler_enable(state),
        is_on_fn=lambda client: client.current_status["steam_boiler_enable"],
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities and services."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        LaMarzoccoSwitchEntity(coordinator, hass, description)
        for description in ENTITIES
        if not description.extra_attributes
        or coordinator.data.model_name in description.extra_attributes
    )


class LaMarzoccoSwitchEntity(LaMarzoccoEntity, SwitchEntity):
    """Switches representing espresso machine power, prebrew, and auto on/off."""

    entity_description: LaMarzoccoSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        await self.entity_description.control_fn(self._lm_client, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        await self.entity_description.control_fn(self._lm_client, False)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.is_on_fn(self._lm_client)
