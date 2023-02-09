"""Support for monitoring Trydan Charger."""
# pylint: disable=no-member
# pylint: disable=overridden-final-method


from dataclasses import dataclass
import logging
import time
from typing import Any

from requests import RequestException
from v2ctrydan import modbus_trydan

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHARGE_ENERGY_KEY,
    CHARGE_POWER_KEY,
    CHARGE_STATE_KEY,
    CHARGE_TIME_KEY,
    CONTRACTED_POWER_READ_KEY,
    DYNAMIC_POWER_MODE_READ_KEY,
    DYNAMIC_READ_KEY,
    FV_POWER_KEY,
    HOUSE_POWER_KEY,
    INTENSITY_READ_KEY,
    LOCK_READ_KEY,
    MAX_INTENSITY_READ_KEY,
    MIN_INTENSITY_READ_KEY,
    OCPP_READ_KEY,
    PAUSE_DYNAMIC_READ_KEY,
    PAUSE_STATE_READ_KEY,
    PAYMENT_READ_KEY,
    PROMGRAM_READ_KEY,
    PWM_VALUE_KEY,
    SLAVE_ERROR_KEY,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SensorEntityDescriptionV2C(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Any = None


TRYDAN_SENSOR_TYPES: tuple[SensorEntityDescriptionV2C, ...] = (
    SensorEntityDescriptionV2C(
        key=CHARGE_STATE_KEY,
        name="Charge State",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:ev-station",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=CHARGE_ENERGY_KEY,
        name="Charge Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=INTENSITY_READ_KEY,
        name="Intensity",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=CHARGE_POWER_KEY,
        name="Charge Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=SLAVE_ERROR_KEY,
        name="Slave Error",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:message-alert",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=CHARGE_TIME_KEY,
        name="Charge Time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:home-clock-outline",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=PWM_VALUE_KEY,
        name="ADC PWM value",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:signal-variant",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=HOUSE_POWER_KEY,
        name="House Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=FV_POWER_KEY,
        name="PV Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=PAUSE_STATE_READ_KEY,
        name="Pause State",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:pause-circle-outline",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=LOCK_READ_KEY,
        name="Lock",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lock",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=PROMGRAM_READ_KEY,
        name="Promgram",
        entity_category=EntityCategory.DIAGNOSTIC,
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=DYNAMIC_READ_KEY,
        name="Dynamic",
        entity_category=EntityCategory.DIAGNOSTIC,
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=PAYMENT_READ_KEY,
        name="Payment",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:credit-card-outline",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=OCPP_READ_KEY,
        name="Ocpp",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:car-electric-outline",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=MIN_INTENSITY_READ_KEY,
        name="Minimum Intensity",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chevron-triple-down",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=MAX_INTENSITY_READ_KEY,
        name="Maximum Intensity",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:chevron-triple-up",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=PAUSE_DYNAMIC_READ_KEY,
        name="Pause Dynamic state",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:play-pause",
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=DYNAMIC_POWER_MODE_READ_KEY,
        name="Dynamic Power",
        entity_category=EntityCategory.DIAGNOSTIC,
        value="0",
    ),
    SensorEntityDescriptionV2C(
        key=CONTRACTED_POWER_READ_KEY,
        name="Contractedd Power state",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        value="0",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the v2c sensor."""
    host = config_entry.data[CONF_HOST]
    charger = modbus_trydan.Charger(host)
    entities = [SensorV2C(charger, description) for description in TRYDAN_SENSOR_TYPES]
    async_add_entities(entities)


class SensorV2C(SensorEntity):
    """Defines a SensorV2C energy sensor."""

    def __init__(self, charger, description: SensorEntityDescriptionV2C) -> None:
        """Initialize the V2C sensor."""
        self.entity_description = description
        self.charger = charger
        self.value = self.entity_description.value

    @property  # type: ignore[misc]
    def state(self) -> float | int | str | None:
        """Return the state of the sensor."""
        return self.value

    def update(self) -> None:  # noqa: C901
        """Get the latest data from the Trydan charger and update the state."""
        try:
            sensor_type = self.entity_description.key

            if sensor_type == CHARGE_STATE_KEY:
                time.sleep(2)
                self.value = self.charger.getChargeState()
                # More specific description of the value:
                if self.value == 0.0:
                    self.value = "A"
                elif self.value == 1.0:
                    self.value = "B"
                elif self.value == 2.0:
                    self.value = "C"

            elif sensor_type == CHARGE_ENERGY_KEY:
                time.sleep(2)
                self.value = self.charger.getChargeEnergy()

            elif sensor_type == INTENSITY_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getIntensity()

            elif sensor_type == CHARGE_POWER_KEY:
                time.sleep(2)
                self.value = self.charger.getChargePower()

            elif sensor_type == SLAVE_ERROR_KEY:
                time.sleep(2)
                self.value = self.charger.getSlaveError()
                # More specific description of the value:
                if self.value == 0.0:
                    self.value = "No error"
                elif self.value == 1.0:
                    self.value = "Error message"
                elif self.value == 2.0:
                    self.value = "Communication error"

            elif sensor_type == CHARGE_TIME_KEY:
                time.sleep(2)
                self.value = self.charger.getChargeTime()

            elif sensor_type == PWM_VALUE_KEY:
                time.sleep(2)
                self.value = self.charger.getValuePWM()

            elif sensor_type == HOUSE_POWER_KEY:
                time.sleep(2)
                self.value = self.charger.getHousePower()

            elif sensor_type == FV_POWER_KEY:
                time.sleep(2)
                self.value = self.charger.getPowerFV()

            elif sensor_type == PAUSE_STATE_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getPauseState()

            elif sensor_type == LOCK_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getLock()

            elif sensor_type == PROMGRAM_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getPromgram()

            elif sensor_type == DYNAMIC_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getDynamic()

            elif sensor_type == PAYMENT_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getPayment()

            elif sensor_type == OCPP_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getOCPP()

            elif sensor_type == MIN_INTENSITY_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getMinIntensity()

            elif sensor_type == MAX_INTENSITY_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getMaxIntensity()

            elif sensor_type == PAUSE_DYNAMIC_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getPauseDynamic()
                # More specific description of the value:
                if self.value == 0.0:
                    self.value = "Dynamic Control Modulation Working"
                elif self.value == 1.0:
                    self.value = "Dynamic Control Modulation Pause"

            elif sensor_type == DYNAMIC_POWER_MODE_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getDynamicPowerMode()
                # More specific description of the value:
                if self.value == 0.0:
                    self.value = "Timed Power enabled"
                elif self.value == 1:
                    self.value = "Timed Power Disabled"
                elif self.value == 2:
                    self.value = "Timed Power Disabled and Exclusive Mode set"
                elif self.value == 3:
                    self.value = "Timed Power Disabled and Min Power Mode set"
                elif self.value == 4:
                    self.value = "Timed Power Disabled and Grid+FV Mode set"
                elif self.value == 5:
                    self.value = "Timed Power Disabled and Stop Mode set"

            elif sensor_type == CONTRACTED_POWER_READ_KEY:
                time.sleep(2)
                self.value = self.charger.getContractedPower()
                # More specific description of the value:
                if self.value == -1.0:
                    self.value = "Inaccessible or unavailable"
                else:
                    self.value = self.charger.getContractedPower()

            else:
                self.value = "Unknown"

        except (RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
