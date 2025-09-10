"""Support for Haus-Bus temperatur sensor."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.de.hausbus.homeassistant.proxy.AnalogEingang import AnalogEingang
from pyhausbus.de.hausbus.homeassistant.proxy.analogEingang.data.Configuration import (
    Configuration as AnalogEingangConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.analogEingang.data.EvStatus import (
    EvStatus as AnalogEingangEvStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.analogEingang.data.Status import (
    Status as AnalogEingangStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Feuchtesensor import Feuchtesensor
from pyhausbus.de.hausbus.homeassistant.proxy.feuchtesensor.data.Configuration import (
    Configuration as FeuchteSensorConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.feuchtesensor.data.EvStatus import (
    EvStatus as FeuchtesensorEvStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.feuchtesensor.data.Status import (
    Status as FeuchtesensorStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Helligkeitssensor import Helligkeitssensor
from pyhausbus.de.hausbus.homeassistant.proxy.helligkeitssensor.data.Configuration import (
    Configuration as HelligkeitsSensorConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.helligkeitssensor.data.EvStatus import (
    EvStatus as HelligkeitssensorEvStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.helligkeitssensor.data.Status import (
    Status as HelligkeitssensorStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.PowerMeter import PowerMeter
from pyhausbus.de.hausbus.homeassistant.proxy.powerMeter.data.Configuration import (
    Configuration as PowerMeterConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.powerMeter.data.EvStatus import (
    EvStatus as PowerMeterEvStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.powerMeter.data.Status import (
    Status as PowerMeterStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.RFIDReader import RFIDReader
from pyhausbus.de.hausbus.homeassistant.proxy.rFIDReader.data.EvData import (
    EvData as RfidEvData,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rFIDReader.data.EvError import (
    EvError as RfidEvError,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Temperatursensor import Temperatursensor
from pyhausbus.de.hausbus.homeassistant.proxy.temperatursensor.data.Configuration import (
    Configuration as TemperaturSensorConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.temperatursensor.data.EvStatus import (
    EvStatus as TemperatursensorEvStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.temperatursensor.data.Status import (
    Status as TemperatursensorStatus,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import HausbusDevice
from .entity import HausbusEntity

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import HausbusConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Haus-Bus sensor from a config entry."""

    gateway = config_entry.runtime_data.gateway

    # Services gelten für alle HausbusLight-Entities, die die jeweilige Funktion implementieren
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "temperatur_sensor_set_configuration",
        {
            vol.Required("correction", default=0.0): vol.All(
                vol.Coerce(float), vol.Range(min=-10, max=10)
            ),
            vol.Required("auto_event_diff", default=0.5): vol.All(
                vol.Coerce(float), vol.Range(min=0.1, max=20)
            ),
            vol.Required("manual_event_interval", default="5 minutes"): vol.In(
                [
                    "1 second",
                    "5 seconds",
                    "10 seconds",
                    "30 seconds",
                    "1 minute",
                    "5 minutes",
                    "10 minutes",
                    "20 minutes",
                    "30 minutes",
                    "60 minutes",
                ]
            ),
        },
        "async_temperatur_sensor_set_configuration",
    )

    platform.async_register_entity_service(
        "power_meter_set_configuration",
        {
            vol.Required("correction", default=0.0): vol.All(
                vol.Coerce(float), vol.Range(min=-10, max=10)
            ),
            vol.Required("auto_event_diff", default=0.5): vol.All(
                vol.Coerce(float), vol.Range(min=0.1, max=20)
            ),
            vol.Required("manual_event_interval", default="5 minutes"): vol.In(
                [
                    "1 second",
                    "5 seconds",
                    "10 seconds",
                    "30 seconds",
                    "1 minute",
                    "5 minutes",
                    "10 minutes",
                    "20 minutes",
                    "30 minutes",
                    "60 minutes",
                ]
            ),
        },
        "async_power_meter_set_configuration",
    )

    platform.async_register_entity_service(
        "brightness_sensor_set_configuration",
        {
            vol.Required("correction", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=-100, max=100)
            ),
            vol.Required("auto_event_diff", default=30): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Required("manual_event_interval", default="5 minutes"): vol.In(
                [
                    "1 second",
                    "5 seconds",
                    "10 seconds",
                    "30 seconds",
                    "1 minute",
                    "5 minutes",
                    "10 minutes",
                    "20 minutes",
                    "30 minutes",
                    "60 minutes",
                ]
            ),
        },
        "async_brightness_sensor_set_configuration",
    )

    platform.async_register_entity_service(
        "humidity_sensor_set_configuration",
        {
            vol.Required("correction", default=0): vol.All(
                vol.Coerce(float), vol.Range(min=-100, max=100)
            ),
            vol.Required("auto_event_diff", default=1): vol.All(
                vol.Coerce(float), vol.Range(min=0.1, max=100)
            ),
            vol.Required("manual_event_interval", default="5 minutes"): vol.In(
                [
                    "1 second",
                    "5 seconds",
                    "10 seconds",
                    "30 seconds",
                    "1 minute",
                    "5 minutes",
                    "10 minutes",
                    "20 minutes",
                    "30 minutes",
                    "60 minutes",
                ]
            ),
        },
        "async_humidity_sensor_set_configuration",
    )

    platform.async_register_entity_service(
        "analog_eingang_set_configuration",
        {
            vol.Required("correction", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=-100, max=100)
            ),
            vol.Required("auto_event_diff", default=10): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required("manual_event_interval", default="5 minutes"): vol.In(
                [
                    "1 second",
                    "5 seconds",
                    "10 seconds",
                    "30 seconds",
                    "1 minute",
                    "5 minutes",
                    "10 minutes",
                    "20 minutes",
                    "30 minutes",
                    "60 minutes",
                ]
            ),
        },
        "async_analog_eingang_set_configuration",
    )

    # Registriere Callback für neue Sensor-Entities
    async def async_add_sensor(channel: HausbusEntity) -> None:
        """Add temperatur sensor from Haus-Bus."""
        if isinstance(channel, HausbusSensor):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_sensor, SENSOR_DOMAIN)


class HausbusSensor(HausbusEntity, SensorEntity):
    """Representation of a Haus-Bus sensor."""

    def __init__(self, channel: ABusFeature, device: HausbusDevice) -> None:
        """Set up sensor."""
        super().__init__(channel, device)

        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = None

    @staticmethod
    def getTimeIntervalMapping(key):
        """Lookup-Funktion, die zu einem Internal Base und Value liefert oder zum Tupel den Value"""

        mapping = {
            "1 second": (1, 1),
            "5 seconds": (1, 5),
            "10 seconds": (1, 10),
            "30 seconds": (1, 30),
            "1 minute": (1, 60),
            "5 minutes": (2, 150),
            "10 minutes": (6, 100),
            "20 minutes": (6, 200),
            "30 minutes": (9, 200),
            "60 minutes": (20, 180),
            "Unknown": (2, 150),
        }

        if isinstance(key, str):
            return mapping.get(key, "Unknown")

        result = next((k for k, (a, b) in mapping.items() if a * b == key), "Unknown")
        if result == "Unknown":
            for front, (a, b) in mapping.items():
                produkt = a * b
                LOGGER.debug("%s %s: %s", key, front, produkt)
        return result


class HausbusTemperaturSensor(HausbusSensor):
    """Representation of a Haus-Bus Temperatursensor."""

    def __init__(self, channel: Temperatursensor, device: HausbusDevice) -> None:
        """Set up sensor."""
        super().__init__(channel, device)

        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_value = None

    def handle_event(self, data: Any) -> None:
        """Handle temperatur sensor events from Haus-Bus."""

        if isinstance(data, (TemperatursensorEvStatus, TemperatursensorStatus)):
            value = float(data.getCelsius()) + float(data.getCentiCelsius()) / 100
            LOGGER.debug("Temperatur empfangen: %s C", value)
            self._attr_native_value = value
            self.schedule_update_ha_state()
        elif isinstance(data, TemperaturSensorConfiguration):
            self._configuration = data

            self._attr_extra_state_attributes["correction"] = data.getCalibration() / 10
            self._attr_extra_state_attributes["auto_event_diff"] = (
                data.getHysteresis() / 10
            )
            self._attr_extra_state_attributes["manual_event_interval"] = (
                HausbusSensor.getTimeIntervalMapping(
                    data.getReportTimeBase() * data.getMaxReportTime()
                )
            )
            LOGGER.debug(
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    @callback
    async def async_temperatur_sensor_set_configuration(
        self, correction: float, auto_event_diff: float, manual_event_interval: str
    ):
        """Setzt die Konfiguration eines Temperatursensors."""
        LOGGER.debug(
            "async_temperatur_sensor_set_configuration correction %s, auto_event_diff %s, manual_event_interval %s", correction, auto_event_diff, manual_event_interval
        )

        if not await self.ensure_configuration():
            raise HomeAssistantError(
                "Configuration could not be read. Please repeat command."
            )

        reportTimeBase, maxReportTime = HausbusSensor.getTimeIntervalMapping(
            manual_event_interval
        )
        self._channel.setConfiguration(
            self._configuration.getLowerThreshold(),
            self._configuration.getLowerThresholdFraction(),
            self._configuration.getUpperThreshold(),
            self._configuration.getUpperThresholdFraction(),
            reportTimeBase,
            1,
            maxReportTime,
            int(auto_event_diff * 10),
            int(correction * 10),
            0,
        )
        self._channel.getConfiguration()


class HausbusPowerMeter(HausbusSensor):
    """Representation of a Haus-Bus PowerMeter."""

    def __init__(self, channel: PowerMeter, device: HausbusDevice) -> None:
        """Set up sensor."""
        super().__init__(channel, device)

        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_value = None

    def handle_event(self, data: Any) -> None:
        """Handle PowerMeter events from Haus-Bus."""

        if isinstance(data, (PowerMeterEvStatus, PowerMeterStatus)):
            value = float(data.getPower()) + float(data.getCentiPower()) / 100
            LOGGER.debug("Power empfangen: %s kW", value)
            self._attr_native_value = value
            self.schedule_update_ha_state()
        elif isinstance(data, PowerMeterConfiguration):
            self._configuration = data

            self._attr_extra_state_attributes["correction"] = data.getCalibration() / 10
            self._attr_extra_state_attributes["auto_event_diff"] = (
                data.getHysteresis() / 10
            )
            self._attr_extra_state_attributes["manual_event_interval"] = (
                HausbusSensor.getTimeIntervalMapping(
                    data.getReportTimeBase() * data.getMaxReportTime()
                )
            )
            LOGGER.debug(
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    @callback
    async def async_power_meter_set_configuration(
        self, correction: float, auto_event_diff: float, manual_event_interval: str
    ):
        """Setzt die Konfiguration eines LogicalButton."""
        LOGGER.debug(
            "async_power_meter_set_configuration correction %s, auto_event_diff %s, manual_event_interval %s", correction, auto_event_diff, manual_event_interval
        )

        if not await self.ensure_configuration():
            raise HomeAssistantError(
                "Configuration could not be read. Please repeat command."
            )

        reportTimeBase, maxReportTime = HausbusSensor.getTimeIntervalMapping(
            manual_event_interval
        )
        self._channel.setConfiguration(
            self._configuration.getLowerThreshold(),
            self._configuration.getLowerThresholdFraction(),
            self._configuration.getUpperThreshold(),
            self._configuration.getUpperThresholdFraction(),
            reportTimeBase,
            1,
            maxReportTime,
            int(auto_event_diff * 10),
            int(correction * 10),
            0,
        )
        self._channel.getConfiguration()


class HausbusBrightnessSensor(HausbusSensor):
    """Representation of a Haus-Bus HelligkeitsSensor."""

    def __init__(self, channel: Helligkeitssensor, device: HausbusDevice) -> None:
        """Set up sensor."""
        super().__init__(channel, device)

        self._attr_native_unit_of_measurement = LIGHT_LUX
        self._attr_device_class = SensorDeviceClass.ILLUMINANCE
        self._attr_native_value = None

    def handle_event(self, data: Any) -> None:
        """Handle brightness sensor events from Haus-Bus."""

        if isinstance(data, (HelligkeitssensorEvStatus, HelligkeitssensorStatus)):
            value = float(data.getBrightness())
            LOGGER.debug("Helligkeit empfangen: %s lx", value)
            self._attr_native_value = value
            self.schedule_update_ha_state()
        elif isinstance(data, HelligkeitsSensorConfiguration):
            self._configuration = data

            self._attr_extra_state_attributes["correction"] = data.getCalibration() * 10
            self._attr_extra_state_attributes["auto_event_diff"] = (
                data.getHysteresis() * 10
            )
            self._attr_extra_state_attributes["manual_event_interval"] = (
                HausbusSensor.getTimeIntervalMapping(
                    data.getReportTimeBase() * data.getMaxReportTime()
                )
            )
            LOGGER.debug(
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    @callback
    async def async_brightness_sensor_set_configuration(
        self, correction: float, auto_event_diff: float, manual_event_interval: str
    ):
        """Setzt die Konfiguration eines Helligkeitssensors."""
        LOGGER.debug(
            "async_brightness_sensor_set_configuration correction %s, auto_event_diff %s, manual_event_interval %s", correction, auto_event_diff, manual_event_interval
        )

        if not await self.ensure_configuration():
            raise HomeAssistantError(
                "Configuration could not be read. Please repeat command."
            )

        reportTimeBase, maxReportTime = HausbusSensor.getTimeIntervalMapping(
            manual_event_interval
        )
        self._channel.setConfiguration(
            self._configuration.getLowerThreshold(),
            self._configuration.getUpperThreshold(),
            reportTimeBase,
            1,
            maxReportTime,
            int(auto_event_diff / 10),
            int(correction / 10),
            0,
        )
        self._channel.getConfiguration()


class HausbusHumiditySensor(HausbusSensor):
    """Representation of a Haus-Bus humidity sensor."""

    def __init__(self, channel: Feuchtesensor, device: HausbusDevice) -> None:
        """Set up sensor."""
        super().__init__(channel, device)

        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_native_value = None

    def handle_event(self, data: Any) -> None:
        """Handle humidity sensor events from Haus-Bus."""

        if isinstance(data, (FeuchtesensorEvStatus, FeuchtesensorStatus)):
            value = (
                float(data.getRelativeHumidity()) + float(data.getCentiHumidity()) / 100
            )
            LOGGER.debug("Feuchtigkeit empfangen: %s %", value)
            self._attr_native_value = value
            self.schedule_update_ha_state()
        elif isinstance(data, FeuchteSensorConfiguration):
            self._configuration = data

            self._attr_extra_state_attributes["correction"] = data.getCalibration() / 10
            self._attr_extra_state_attributes["auto_event_diff"] = (
                data.getHysteresis() / 10
            )
            self._attr_extra_state_attributes["manual_event_interval"] = (
                HausbusSensor.getTimeIntervalMapping(
                    data.getReportTimeBase() * data.getMaxReportTime()
                )
            )
            LOGGER.debug(
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    @callback
    async def async_humidity_sensor_set_configuration(
        self, correction: float, auto_event_diff: float, manual_event_interval: str
    ):
        """Sets configuration of a humidity sensor"""
        LOGGER.debug(
            "async_humidity_sensor_set_configuration correction %s, auto_event_diff %s, manual_event_interval %s", correction, auto_event_diff, manual_event_interval
        )

        if not await self.ensure_configuration():
            raise HomeAssistantError(
                "Configuration could not be read. Please repeat command."
            )

        reportTimeBase, maxReportTime = HausbusSensor.getTimeIntervalMapping(
            manual_event_interval
        )
        self._channel.setConfiguration(
            self._configuration.getLowerThreshold(),
            self._configuration.getLowerThresholdFraction(),
            self._configuration.getUpperThreshold(),
            self._configuration.getUpperThresholdFraction(),
            reportTimeBase,
            1,
            maxReportTime,
            int(auto_event_diff * 10),
            int(correction * 10),
            0,
        )
        self._channel.getConfiguration()


class HausbusAnalogEingang(HausbusSensor):
    """Representation of a Haus-Bus analog input."""

    def __init__(self, channel: AnalogEingang, device: HausbusDevice) -> None:
        """Set up sensor."""
        super().__init__(channel, device)

        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_native_value = None

    def handle_event(self, data: Any) -> None:
        """Handle AnalogEingang events from Haus-Bus."""

        if isinstance(data, (AnalogEingangEvStatus, AnalogEingangStatus)):
            value = data.getValue()
            LOGGER.debug("Analogwert empfangen: %s", value)
            self._attr_native_value = value
            self.schedule_update_ha_state()
        elif isinstance(data, AnalogEingangConfiguration):
            self._configuration = data

            self._attr_extra_state_attributes["correction"] = data.getCalibration()
            self._attr_extra_state_attributes["auto_event_diff"] = data.getHysteresis()
            self._attr_extra_state_attributes["manual_event_interval"] = (
                HausbusSensor.getTimeIntervalMapping(
                    data.getReportTimeBase() * data.getMaxReportTime()
                )
            )
            LOGGER.debug(
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    @callback
    async def async_analog_eingang_set_configuration(
        self, correction: float, auto_event_diff: float, manual_event_interval: str
    ):
        """Setzt die Konfiguration eines Analogeingangs."""
        LOGGER.debug(
            "async_analog_eingang_set_configuration correction %s, auto_event_diff %s, manual_event_interval %s", correction, auto_event_diff, manual_event_interval
        )

        if not await self.ensure_configuration():
            raise HomeAssistantError(
                "Configuration could not be read. Please repeat command."
            )

        reportTimeBase, maxReportTime = HausbusSensor.getTimeIntervalMapping(
            manual_event_interval
        )
        self._channel.setConfiguration(
            self._configuration.getLowerThreshold(),
            self._configuration.getUpperThreshold(),
            reportTimeBase,
            1,
            maxReportTime,
            auto_event_diff,
            correction,
            0,
        )
        self._channel.getConfiguration()


class HausbusRfidSensor(HausbusSensor):
    """Representation of a Haus-Bus RFID reader."""

    def __init__(self, channel: RFIDReader, device: HausbusDevice) -> None:
        """Set up sensor."""
        super().__init__(channel, device)

        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_native_value = None

    def get_hardware_status(self) -> None:
        """Overriding base class to suppress getStatus calls"""

    def handle_event(self, data: Any) -> None:
        """Handle rfid events from Haus-Bus."""

        if isinstance(data, RfidEvData):
            LOGGER.debug("rfid data: %s", data)
            self._attr_native_value = data.getTagID()

            self._attr_extra_state_attributes["last_tag"] = self._attr_native_value
            self._attr_extra_state_attributes["last_time"] = datetime.now().isoformat()
            self._attr_extra_state_attributes["last_error"] = ""
            self.schedule_update_ha_state()

        elif isinstance(data, RfidEvError):
            LOGGER.debug("rfid error: %s", data)
            self._attr_extra_state_attributes["last_tag"] = ""
            self._attr_extra_state_attributes["last_time"] = datetime.now().isoformat()
            self._attr_extra_state_attributes["last_error"] = data.getErrorCode()
