"""Support for monitoring Trydan Charger."""
from __future__ import annotations

import logging

from requests import RequestException
import v2ctrydan
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CHARGE_ENERGY_KEY,
    CHARGE_POWER_KEY,
    CHARGE_STATE_KEY,
    CHARGE_TIME_KEY,
    DYNAMIC_KEY,
    DYNAMIC_READ_KEY,
    FV_POWER_KEY,
    HOUSE_POWER_KEY,
    INTENSITY_KEY,
    INTENSITY_READ_KEY,
    LOCK_KEY,
    LOCK_READ_KEY,
    OCPP_KEY,
    OCPP_READ_KEY,
    PAUSE_STATE_KEY,
    PAUSE_STATE_READ_KEY,
    PAYMENT_KEY,
    PAYMENT_READ_KEY,
    PROMGRAM_KEY,
    PROMGRAM_READ_KEY,
    PWM_VALUE_KEY,
    SLAVE_ERROR_KEY,
)

# pylint: disable=no-member

_LOGGER = logging.getLogger(__name__)

TRYDAN_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CHARGE_STATE_KEY,
        name="Charge State Trydan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=CHARGE_POWER_KEY,
        name="Charge Power Trydan",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=CHARGE_ENERGY_KEY,
        name="Charge Energy Trydan",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=SLAVE_ERROR_KEY,
        name="Slave Error Trydan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=CHARGE_TIME_KEY,
        name="Charge Time Trydan",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=PWM_VALUE_KEY,
        name="ADC PWM value Trydan",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=HOUSE_POWER_KEY,
        name="House Power Trydan",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=FV_POWER_KEY,
        name="PV Power Trydan",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=PAUSE_STATE_READ_KEY,
        name="Pause State Read",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=LOCK_READ_KEY,
        name="Lock Read",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=PROMGRAM_READ_KEY,
        name="Promgram Read",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=INTENSITY_READ_KEY,
        name="Intensity Read",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=DYNAMIC_READ_KEY,
        name="Dynamic Read",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=PAYMENT_READ_KEY,
        name="Payment Read",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=OCPP_READ_KEY,
        name="Ocpp Read",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=PAUSE_STATE_KEY,
        name="Pause state",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=LOCK_KEY,
        name="Lock state Trydan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=PROMGRAM_KEY,
        name="Promgram state Trydan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=INTENSITY_KEY,
        name="Trydan Intensity",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=DYNAMIC_KEY,
        name="Trydan Dynamic",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=PAYMENT_KEY,
        name="Trydan payment",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=OCPP_KEY,
        name="OCPP state Trydan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in TRYDAN_SENSOR_TYPES]


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["status"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Trydan sensor."""
    host = config[CONF_HOST]
    monitored_variables = config[CONF_MONITORED_VARIABLES]

    charger = v2ctrydan.Charger(host)

    entities = [
        SensorV2C(charger, description)
        for description in (TRYDAN_SENSOR_TYPES)
        if description.key in monitored_variables
    ]

    add_entities(entities, True)


class SensorV2C(SensorEntity):
    """Defines a SensorV2C energy sensor."""

    def __init__(
        self,
        charger,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the V2C sensor."""
        self.entity_description = description
        self.charger = charger

    def update(self) -> None:
        """Get the monitored data from the Trydan charger."""
        try:
            sensor_type = self.entity_description.key
            if sensor_type == CHARGE_STATE_KEY:
                self._attr_native_value = self.charger.getChargeState()
            elif sensor_type == CHARGE_POWER_KEY:
                self._attr_native_value = self.charger.getChargePower()
            elif sensor_type == CHARGE_ENERGY_KEY:
                self._attr_native_value = self.charger.getChargeEnergy()
            elif sensor_type == SLAVE_ERROR_KEY:
                self._attr_native_value = self.charger.getSlaveError()
            elif sensor_type == CHARGE_TIME_KEY:
                self._attr_native_value = self.charger.getChargeTime()
            elif sensor_type == PWM_VALUE_KEY:
                self._attr_native_value = self.charger.getValuePWM()
            elif sensor_type == HOUSE_POWER_KEY:
                self._attr_native_value = self.charger.getHousePower()
            elif sensor_type == FV_POWER_KEY:
                self._attr_native_value = self.charger.getPowerFV()
            elif sensor_type == PAUSE_STATE_READ_KEY:
                self._attr_native_value = self.charger.getPauseState()
            elif sensor_type == LOCK_READ_KEY:
                self._attr_native_value = self.charger.getLock()
            elif sensor_type == PROMGRAM_READ_KEY:
                self._attr_native_value = self.charger.getPromgram()
            elif sensor_type == INTENSITY_READ_KEY:
                self._attr_native_value = self.charger.getIntensity()
            elif sensor_type == DYNAMIC_READ_KEY:
                self._attr_native_value = self.charger.getDynamic()
            elif sensor_type == PAYMENT_READ_KEY:
                self._attr_native_value = self.charger.getPayment()
            elif sensor_type == OCPP_READ_KEY:
                self._attr_native_value = self.charger.getOCPP()
            elif sensor_type == PAUSE_STATE_KEY:
                self._attr_native_value = self.charger.postPauseState()
            elif sensor_type == LOCK_KEY:
                self._attr_native_value = self.charger.postLock()
            elif sensor_type == PROMGRAM_KEY:
                self._attr_native_value = self.charger.postPromgram()
            elif sensor_type == INTENSITY_KEY:
                self._attr_native_value = self.charger.postIntensity()
            elif sensor_type == DYNAMIC_KEY:
                self._attr_native_value = self.charger.postDynamic()
            elif sensor_type == PAYMENT_KEY:
                self._attr_native_value = self.charger.postPayment()
            elif sensor_type == OCPP_KEY:
                self._attr_native_value = self.charger.postOcpp()
            else:
                self._attr_native_value = "Unknown"
        except (RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
