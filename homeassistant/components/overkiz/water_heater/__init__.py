"""Support for Overkiz water heater devices."""

from __future__ import annotations

from pyoverkiz.enums.ui import UIWidget

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .. import OverkizDataConfigEntry
from ..entity import OverkizEntity
from .atlantic_domestic_hot_water_production_mlb_component import (
    AtlanticDomesticHotWaterProductionMBLComponent,
)
from .atlantic_domestic_hot_water_production_v2_io_component import (
    AtlanticDomesticHotWaterProductionV2IOComponent,
)
from .atlantic_pass_apc_dhw import AtlanticPassAPCDHW
from .domestic_hot_water_production import DomesticHotWaterProduction
from .hitachi_dhw import HitachiDHW


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz DHW from a config entry."""
    data = entry.runtime_data
    entities: list[OverkizEntity] = []

    for device in data.platforms[Platform.WATER_HEATER]:
        if device.controllable_name in CONTROLLABLE_NAME_TO_WATER_HEATER_ENTITY:
            entities.append(
                CONTROLLABLE_NAME_TO_WATER_HEATER_ENTITY[device.controllable_name](
                    device.device_url, data.coordinator
                )
            )
        elif device.widget in WIDGET_TO_WATER_HEATER_ENTITY:
            entities.append(
                WIDGET_TO_WATER_HEATER_ENTITY[device.widget](
                    device.device_url, data.coordinator
                )
            )

    async_add_entities(entities)


WIDGET_TO_WATER_HEATER_ENTITY = {
    UIWidget.ATLANTIC_PASS_APC_DHW: AtlanticPassAPCDHW,
    UIWidget.DOMESTIC_HOT_WATER_PRODUCTION: DomesticHotWaterProduction,
    UIWidget.HITACHI_DHW: HitachiDHW,
}

CONTROLLABLE_NAME_TO_WATER_HEATER_ENTITY = {
    "modbuslink:AtlanticDomesticHotWaterProductionMBLComponent": AtlanticDomesticHotWaterProductionMBLComponent,
    "io:AtlanticDomesticHotWaterProductionV2_CV4E_IOComponent": AtlanticDomesticHotWaterProductionV2IOComponent,
}
