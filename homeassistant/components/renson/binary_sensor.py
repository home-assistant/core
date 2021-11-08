"""Binary sensors for renson."""
from rensonVentilationLib.fieldEnum import (
    AIR_QUALITY_CONTROL_FIELD,
    BREEZE_ENABLE_FIELD,
    BREEZE_MET_FIELD,
    CO2_CONTROL_FIELD,
    FROST_PROTECTION_FIELD,
    HUMIDITY_CONTROL_FIELD,
    PREHEATER_FIELD,
)
import rensonVentilationLib.renson as renson

from homeassistant.components.renson.renson_binary_sensor import RensonBinarySensor
from homeassistant.components.renson.renson_descriptions import (
    RensonBinarySensorEntityDescription,
)
from homeassistant.components.renson.renson_firmware_sensor import FirmwareSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

binary_sensor_descriptions = [
    RensonBinarySensorEntityDescription(
        key="FROST_PROTECTION_FIELD",
        name="Frost protection active",
        field=FROST_PROTECTION_FIELD,
    ),
    RensonBinarySensorEntityDescription(
        key="BREEZE_ENABLE_FIELD",
        name="Breeze",
        field=BREEZE_ENABLE_FIELD,
    ),
    RensonBinarySensorEntityDescription(
        key="BREEZE_MET_FIELD",
        name="Breeze conditions met",
        field=BREEZE_MET_FIELD,
    ),
    RensonBinarySensorEntityDescription(
        key="HUMIDITY_CONTROL_FIELD",
        name="Humidity control",
        field=HUMIDITY_CONTROL_FIELD,
    ),
    RensonBinarySensorEntityDescription(
        key="AIR_QUALITY_CONTROL_FIELD",
        name="Air quality control",
        field=AIR_QUALITY_CONTROL_FIELD,
    ),
    RensonBinarySensorEntityDescription(
        key="CO2_CONTROL_FIELD",
        name="CO2 control",
        field=CO2_CONTROL_FIELD,
    ),
    RensonBinarySensorEntityDescription(
        key="PREHEATER_FIELD",
        name="Preheater",
        field=PREHEATER_FIELD,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Call the Renson integration to setup."""
    renson_api: renson.RensonVentilation = hass.data[DOMAIN][config_entry.entry_id]

    entities: list = []
    for description in binary_sensor_descriptions:
        entities.append(RensonBinarySensor(description, renson_api))

    entities.append(FirmwareSensor(renson_api, hass))
    async_add_entities(entities)
