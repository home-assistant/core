"""Binary sensors for renson."""
from renson_endura_delta.field_enum import (
    AIR_QUALITY_CONTROL_FIELD,
    BREEZE_ENABLE_FIELD,
    BREEZE_MET_FIELD,
    CO2_CONTROL_FIELD,
    FROST_PROTECTION_FIELD,
    HUMIDITY_CONTROL_FIELD,
    PREHEATER_FIELD,
    FieldEnum,
)
from renson_endura_delta.renson import RensonVentilation

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


class RensonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of binary sensor."""

    def __init__(
        self,
        key: str,
        name: str,
        field: FieldEnum,
        entity_registry_enabled_default: bool = True,
    ) -> None:
        """Initialize class."""
        super().__init__(
            key=key,
            entity_registry_enabled_default=entity_registry_enabled_default,
        )

        self.name = name
        self.field = field


class RensonBinarySensor(BinarySensorEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        description: RensonBinarySensorEntityDescription,
        renson_api: RensonVentilation,
    ) -> None:
        """Initialize class."""
        self._state = None
        self.renson = renson_api
        self.field = description.field
        self.entity_description = description

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def update(self):
        """Get binary data and save it in state."""
        self._state = self.renson.get_data_boolean(self.field)


class FirmwareSensor(BinarySensorEntity):
    """Check firmware update and store it in the state of the class."""

    def __init__(self, renson_api: RensonVentilation, hass):
        """Initialize class."""
        self._state = None
        self.renson = renson_api
        self.hass = hass

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Latest firmware"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    async def async_update(self):
        """Get firmware and save it in state."""
        self._state = await self.hass.async_add_executor_job(
            self.renson.is_firmware_up_to_date
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Call the Renson integration to setup."""
    renson_api: RensonVentilation = hass.data[DOMAIN][config_entry.entry_id]

    entities: list = []
    for description in binary_sensor_descriptions:
        entities.append(RensonBinarySensor(description, renson_api))

    entities.append(FirmwareSensor(renson_api, hass))
    async_add_entities(entities)


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
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
    ),
    RensonBinarySensorEntityDescription(
        key="AIR_QUALITY_CONTROL_FIELD",
        name="Air quality control",
        field=AIR_QUALITY_CONTROL_FIELD,
        entity_registry_enabled_default=False,
    ),
    RensonBinarySensorEntityDescription(
        key="CO2_CONTROL_FIELD",
        name="CO2 control",
        field=CO2_CONTROL_FIELD,
        entity_registry_enabled_default=False,
    ),
    RensonBinarySensorEntityDescription(
        key="PREHEATER_FIELD",
        name="Preheater",
        field=PREHEATER_FIELD,
    ),
]
