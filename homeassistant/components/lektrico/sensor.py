"""Support for Lektrico charging station sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from lektricowifi import lektricowifi

from homeassistant.components.sensor import (  # https://developers.home-assistant.io/docs/core/entity/sensor/;
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_FRIENDLY_NAME,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_KILO_WATT,
    TEMP_CELSIUS,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=10)


@dataclass
class LektricoSensorEntityDescription(SensorEntityDescription):
    """A class that describes the Lektrico sensor entities."""

    unit_fn: str | None = None
    value_fn: Any | None = None


SENSORS: tuple[LektricoSensorEntityDescription, ...] = (
    LektricoSensorEntityDescription(
        key="charger_state",
        name="Charger_State",
        value_fn=lambda x: x.charger_state,
    ),
    LektricoSensorEntityDescription(
        key="charging_time",
        name="Charging_Time",
        unit_fn=TIME_SECONDS,
        value_fn=lambda x: x.charging_time,
    ),
    LektricoSensorEntityDescription(
        key="current",
        name="Current",
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_CURRENT,
        unit_fn=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda x: x.current,
    ),
    LektricoSensorEntityDescription(
        key="instant_power",
        name="Instant_Power",
        device_class=DEVICE_CLASS_POWER,
        unit_fn=POWER_KILO_WATT,
        value_fn=lambda x: x.instant_power,
    ),
    LektricoSensorEntityDescription(
        key="session_energy",
        name="Session_Energy",
        device_class=DEVICE_CLASS_ENERGY,
        unit_fn=ENERGY_KILO_WATT_HOUR,
        value_fn=lambda x: x.session_energy,
    ),
    LektricoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_TEMPERATURE,
        unit_fn=TEMP_CELSIUS,
        value_fn=lambda x: x.temperature,
    ),
    LektricoSensorEntityDescription(
        key="total_charged_energy",
        name="Total_Charged_Energy",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_ENERGY,
        unit_fn=ENERGY_KILO_WATT_HOUR,
        value_fn=lambda x: x.total_charged_energy,
    ),
    LektricoSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=DEVICE_CLASS_VOLTAGE,
        unit_fn=ELECTRIC_POTENTIAL_VOLT,
        value_fn=lambda x: x.voltage,
    ),
    LektricoSensorEntityDescription(
        key="install_current",
        name="Install_Current",
        device_class=DEVICE_CLASS_CURRENT,
        unit_fn=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda x: x.install_current,
    ),
    LektricoSensorEntityDescription(
        key="dynamic_current",
        name="Dynamic_Current",
        device_class=DEVICE_CLASS_CURRENT,
        unit_fn=ELECTRIC_CURRENT_AMPERE,
        value_fn=lambda x: x.dynamic_current,
    ),
    LektricoSensorEntityDescription(
        key="led_max_brightness",
        name="Led_Brightness",
        device_class=DEVICE_CLASS_ILLUMINANCE,
        value_fn=lambda x: x.led_max_brightness,
    ),
    LektricoSensorEntityDescription(
        key="headless",
        name="No_Authentication",
        value_fn=lambda x: x.headless,
    ),
)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


class LektricoDevice:
    """The device class for Lektrico charger."""

    _last_client_refresh = datetime.min

    def __init__(self, device: lektricowifi.Charger, hass: Any, friendly_name: str):
        """Initialize a Lektrico Device."""
        self._device = device
        self._hass = hass
        self.friendly_name = friendly_name.replace(" ", "_")
        self._name = friendly_name
        self._coordinator: DataUpdateCoordinator | None = None
        self._update_fail_count = 0
        self._info = None

    @property
    def coordinator(self) -> DataUpdateCoordinator | None:
        """Return the coordinator of the Lektrico device."""
        return self._coordinator

    async def init_device(self) -> bool:
        """Init the device status and start coordinator."""

        # Create status update coordinator
        await self._create_coordinator()

        if self._coordinator is None:
            print("coordinator is NONE")
            return False
        else:
            return True

    async def async_device_update(self) -> lektricowifi.Info:
        """Async Update device state."""
        a_data = self._hass.async_add_job(self._device.charger_info)
        data = await a_data
        entity_reg = er.async_get(self._hass)
        my_entry = entity_reg.async_get(f"sensor.{self.friendly_name}_{SENSORS[0].key}")
        # print(f"my_entry= {my_entry}")
        if my_entry is not None:
            dev_reg = dr.async_get(self._hass)
            if my_entry.device_id is not None:
                device = dev_reg.async_get(my_entry.device_id)
                if device is not None:
                    dev_reg.async_update_device(device.id, sw_version=data.fw_version)
                    # print(f"device.sw_version= {device.sw_version}")
        return data

    async def _create_coordinator(self) -> None:
        """Get the coordinator for a specific device."""
        coordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name=f"{DOMAIN}-{self._name}",
            update_method=self.async_device_update,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=SCAN_INTERVAL,
        )
        await coordinator.async_refresh()

        if not coordinator.last_update_success:
            raise ConfigEntryNotReady

        self._coordinator = coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico charger based on a config entry."""
    charger: lektricowifi.Charger = hass.data[DOMAIN][entry.entry_id]
    # print(f"hass= {hass}")
    # print(f"hass.data= {hass.data}")   #f.f.f.f. mare
    # print(f"hass.data[DOMAIN]= {hass.data[DOMAIN]}")
    # {'b66d66f250b9c6f25d9cd488630dacee': {'lektrico_client': Charger(_host='192.168.100.11',
    # request_timeout=8, session=<aiohttp.client.ClientSession object at 0x7ffa67284760>,
    # _close_session=False)}}
    # print(f"entry= {entry}")
    # <homeassistant.config_entries.ConfigEntry object at 0x7ffa892987d0>
    # print(f"entry.entry_id= {entry.entry_id}") #b66d66f250b9c6f25d9cd488630dacee
    # print(f"hass.data[DOMAIN][entry.entry_id]= {hass.data[DOMAIN][entry.entry_id]}")
    # {'lektrico_client': Charger(_host='192.168.100.11', request_timeout=8,
    # session=<aiohttp.client.ClientSession object at 0x7ffa67284760>,
    # _close_session=False)}
    # print(f"hass.data[DOMAIN][entry.entry_id][DATA_LEKTRICO_CLIENT]=
    # {hass.data[DOMAIN][entry.entry_id][DATA_LEKTRICO_CLIENT]}")
    # Charger(_host='192.168.100.11', request_timeout=8,
    # session=<aiohttp.client.ClientSession object at 0x7ffa67284760>,
    # _close_session=False)

    print(f"entry.title={entry.title}")  # entry.title=lek
    print(f"entry.data={entry.data}")
    # entry.data={'host': '192.168.100.11', 'friendly_name': 'lek'}
    print(f"entry.data.friendly_name={entry.data[CONF_FRIENDLY_NAME]}")
    # entry.data.friendly_name=lek

    await charger.charger_info()
    settings = await charger.charger_config()
    _lektrico_device = LektricoDevice(charger, hass, entry.data[CONF_FRIENDLY_NAME])
    if not await _lektrico_device.init_device():
        _LOGGER.error("Error initializing Lektrico Device. Name: 1P7K")

    sensors = []

    sensors.extend(
        [
            LektricoSensor(
                charger,
                sensor_desc,
                settings,
                _lektrico_device,
                entry.data[CONF_FRIENDLY_NAME],
            )
            for sensor_desc in SENSORS
        ]
    )

    async_add_entities(sensors, True)

    # platform = async_get_current_platform()
    # platform.async_register_entity_service(
    #     SERVICE_IDENTIFY,
    #     {},
    #     LektricoSensor.async_identify.__name__,
    # )


# def get_entity_name(device, ent_key, ent_name) -> str:
#     """Get the name for the entity"""
#     name_slug = device.name
#     # if ent_key == DEFAULT_SENSOR:
#     #     return name_slug

#     name = ent_name or ent_key
#     if not ent_name:
#         feat_name = device.available_features.get(ent_key)
#         if feat_name and feat_name != ent_key:
#             name = feat_name.replace("_", " ").capitalize()

#     return f"{name_slug} {name}"


class LektricoSensor(CoordinatorEntity, SensorEntity):
    """The entity class for Lektrico charging stations sensors."""

    entity_description: LektricoSensorEntityDescription

    def __init__(
        self,
        charger: lektricowifi.Charger,
        description: LektricoSensorEntityDescription,
        settings: lektricowifi.Settings,
        _lektrico_device: LektricoDevice,
        friendly_name: str,
    ) -> None:
        """Initialize Lektrico charger."""
        if _lektrico_device.coordinator is None:
            super()
        else:
            super().__init__(_lektrico_device.coordinator)
        self.charger = charger
        self.friendly_name = friendly_name
        print("_init_")
        self.entity_description = description
        # print(f"self.entity_description={self.entity_description}")
        # self._attr_name = get_entity_name(charger, description.key, description.name)

        self._attr_name = f"{self.friendly_name} {description.name}"
        # this is the entity name    #ex: 1P7K Charger_State
        # and it will become the entity id  sensor.<friendly_name>_charger_state
        # ex: sensor.1p7k_charger_state
        print(f"self._attr_name={self._attr_name}")
        self._attr_unique_id = f"{settings.serial_number}_{description.name}"
        # ex: 500006_Led_Brightness
        print(f"self._attr_unique_id={self._attr_unique_id}")
        # print(f"data = {_lektrico_device.coordinator.data}")
        # self._attributes: dict[str, str] = {}

        self._settings = settings
        self._lektrico_device = _lektrico_device

    @property
    def name(self) -> str | None:
        """Return the entity name. ex: 1P7K Charger_State ."""
        return self._attr_name

    @property
    def unique_id(self) -> str | None:
        """Return the unique id of the entity. ex: 500006_Led_Brightness ."""
        return self._attr_unique_id

    @property
    def native_value(self) -> float | str | Any | None:
        """Return the state of the sensor."""
        # print(f"{self.entity_description.name} - {self.entity_description.value_fn}")
        if self.entity_description.value_fn is not None:
            if self._lektrico_device.coordinator is None:
                return None
            else:
                return self.entity_description.value_fn(
                    self._lektrico_device.coordinator.data
                )
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor, if any."""
        # print(f"{self.entity_description.name} - {self.entity_description.unit_fn}")
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn
        return super().native_unit_of_measurement

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Lektrico charger."""
        if self._lektrico_device.coordinator is None:
            return {
                ATTR_IDENTIFIERS: {(DOMAIN, self._settings.serial_number)},
                ATTR_NAME: self.friendly_name,
                ATTR_MANUFACTURER: "Lektrico",
                ATTR_MODEL: f"1P7K {self._settings.serial_number} rev.{self._settings.board_revision}",
            }
        else:
            return {
                ATTR_IDENTIFIERS: {(DOMAIN, self._settings.serial_number)},
                ATTR_NAME: self.friendly_name,
                ATTR_MANUFACTURER: "Lektrico",
                ATTR_MODEL: f"1P7K {self._settings.serial_number} rev.{self._settings.board_revision}",
                # ATTR_SW_VERSION: self._settings.serial_number
                # ATTR_SW_VERSION: f"{self._info.firmware_version}
                # ({self._info.firmware_build_number})",
                ATTR_SW_VERSION: self._lektrico_device.coordinator.data.fw_version,
            }

    # async def async_update(self):
    #     """Update the entity.
    #     Only used by the generic entity update service.
    #     """
    #     print("async_update")
    #     # await self.coordinator.async_request_refresh()

    # async def async_identify(self) -> None:
    #     """Identify the charger, will make it blink."""
    #     # try:
    #     print("identify")
    #     # except ChargerError:
    #     #     _LOGGER.exception("An error occurred while identifying the Lektrico charger")
    #     #     self._state = None
