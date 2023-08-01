"""Support for EDL21 Smart Meters."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from sml import SmlGetListResponse
from sml.asyncio import SmlProtocol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import (
    CONF_SERIAL_PORT,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    LOGGER,
    SIGNAL_EDL21_TELEGRAM,
)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

# OBIS format: A-B:C.D.E*F
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    # A=1: Electricity
    # C=0: General purpose objects
    # D=0: Free ID-numbers for utilities
    # E=0 Ownership ID
    SensorEntityDescription(
        key="1-0:0.0.0*255",
        translation_key="ownership_id",
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    # E=9: Electrity ID
    SensorEntityDescription(
        key="1-0:0.0.9*255",
        translation_key="electricity_id",
        icon="mdi:flash",
    ),
    # D=2: Program entries
    SensorEntityDescription(
        key="1-0:0.2.0*0",
        translation_key="configuration_program_version_number",
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="1-0:0.2.0*1",
        translation_key="firmware_version_number",
        icon="mdi:flash",
    ),
    # C=1: Active power +
    # D=8: Time integral 1
    # E=0: Total
    SensorEntityDescription(
        key="1-0:1.8.0*255",
        translation_key="positive_active_energy_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # E=1: Rate 1
    SensorEntityDescription(
        key="1-0:1.8.1*255",
        translation_key="positive_active_energy_tariff_t1",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # E=2: Rate 2
    SensorEntityDescription(
        key="1-0:1.8.2*255",
        translation_key="positive_active_energy_tariff_t2",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # D=17: Time integral 7
    # E=0: Total
    SensorEntityDescription(
        key="1-0:1.17.0*255",
        translation_key="last_signed_positive_active_energy_total",
    ),
    # C=2: Active power -
    # D=8: Time integral 1
    # E=0: Total
    SensorEntityDescription(
        key="1-0:2.8.0*255",
        translation_key="negative_active_energy_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # E=1: Rate 1
    SensorEntityDescription(
        key="1-0:2.8.1*255",
        translation_key="negative_active_energy_tariff_t1",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # E=2: Rate 2
    SensorEntityDescription(
        key="1-0:2.8.2*255",
        translation_key="negative_active_energy_tariff_t2",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # C=14: Supply frequency
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:14.7.0*255",
        translation_key="supply_frequency",
        icon="mdi:sine-wave",
    ),
    # C=15: Active power absolute
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:15.7.0*255",
        translation_key="absolute_active_instantaneous_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=16: Active power sum
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:16.7.0*255",
        translation_key="sum_active_instantaneous_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=31: Active amperage L1
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:31.7.0*255",
        translation_key="l1_active_instantaneous_amperage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    # C=32: Active voltage L1
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:32.7.0*255",
        translation_key="l1_active_instantaneous_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # C=36: Active power L1
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:36.7.0*255",
        translation_key="l1_active_instantaneous_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=51: Active amperage L2
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:51.7.0*255",
        translation_key="l2_active_instantaneous_amperage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    # C=52: Active voltage L2
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:52.7.0*255",
        translation_key="l2_active_instantaneous_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # C=56: Active power L2
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:56.7.0*255",
        translation_key="l2_active_instantaneous_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=71: Active amperage L3
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:71.7.0*255",
        translation_key="l3_active_instantaneous_amperage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    # C=72: Active voltage L3
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:72.7.0*255",
        translation_key="l3_active_instantaneous_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # C=76: Active power L3
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:76.7.0*255",
        translation_key="l3_active_instantaneous_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=81: Angles
    # D=7: Instantaneous value
    # E=1:  U(L2) x U(L1)
    # E=2:  U(L3) x U(L1)
    # E=4:  U(L1) x I(L1)
    # E=15: U(L2) x I(L2)
    # E=26: U(L3) x I(L3)
    SensorEntityDescription(
        key="1-0:81.7.1*255",
        translation_key="u_l2_u_l1_phase_angle",
        icon="mdi:sine-wave",
    ),
    SensorEntityDescription(
        key="1-0:81.7.2*255",
        translation_key="u_l3_u_l1_phase_angle",
        icon="mdi:sine-wave",
    ),
    SensorEntityDescription(
        key="1-0:81.7.4*255",
        translation_key="u_l1_i_l1_phase_angle",
        icon="mdi:sine-wave",
    ),
    SensorEntityDescription(
        key="1-0:81.7.15*255",
        translation_key="u_l2_i_l2_phase_angle",
        icon="mdi:sine-wave",
    ),
    SensorEntityDescription(
        key="1-0:81.7.26*255",
        translation_key="u_l3_i_l3_phase_angle",
        icon="mdi:sine-wave",
    ),
    # C=96: Electricity-related service entries
    SensorEntityDescription(
        key="1-0:96.1.0*255",
        translation_key="metering_point_id_1",
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="1-0:96.5.0*255",
        translation_key="internal_operating_status",
        icon="mdi:flash",
    ),
)

SENSORS = {desc.key: desc for desc in SENSOR_TYPES}

SENSOR_UNIT_MAPPING = {
    "Wh": UnitOfEnergy.WATT_HOUR,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "W": UnitOfPower.WATT,
    "A": UnitOfElectricCurrent.AMPERE,
    "V": UnitOfElectricPotential.VOLT,
    "°": DEGREE,
    "Hz": UnitOfFrequency.HERTZ,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EDL21 sensor."""
    hass.data[DOMAIN] = EDL21(hass, config_entry.data, async_add_entities)
    await hass.data[DOMAIN].connect()


class EDL21:
    """EDL21 handles telegrams sent by a compatible smart meter."""

    _OBIS_BLACKLIST = {
        # C=96: Electricity-related service entries
        "1-0:96.50.1*1",  # Manufacturer specific EFR SGM-C4 Hardware version
        "1-0:96.50.1*4",  # Manufacturer specific EFR SGM-C4 Hardware version
        "1-0:96.50.4*4",  # Manufacturer specific EFR SGM-C4 Parameters version
        "1-0:96.90.2*1",  # Manufacturer specific EFR SGM-C4 Firmware Checksum
        "1-0:96.90.2*2",  # Manufacturer specific EFR SGM-C4 Firmware Checksum
        # C=97: Electricity-related service entries
        "1-0:97.97.0*0",  # Manufacturer specific EFR SGM-C4 Error register
        # A=129: Manufacturer specific
        "129-129:199.130.3*255",  # Iskraemeco: Manufacturer
        "129-129:199.130.5*255",  # Iskraemeco: Public Key
    }

    def __init__(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any],
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize an EDL21 object."""
        self._registered_obis: set[tuple[str, str]] = set()
        self._hass = hass
        self._async_add_entities = async_add_entities
        self._serial_port = config[CONF_SERIAL_PORT]
        self._proto = SmlProtocol(config[CONF_SERIAL_PORT])
        self._proto.add_listener(self.event, ["SmlGetListResponse"])
        LOGGER.debug(
            "Initialized EDL21 on %s",
            config[CONF_SERIAL_PORT],
        )

    async def connect(self) -> None:
        """Connect to an EDL21 reader."""
        await self._proto.connect(self._hass.loop)

    def event(self, message_body) -> None:
        """Handle events from pysml."""
        assert isinstance(message_body, SmlGetListResponse)
        LOGGER.debug("Received sml message on %s: %s", self._serial_port, message_body)

        electricity_id = message_body["serverId"]

        if electricity_id is None:
            LOGGER.debug(
                "No electricity id found in sml message on %s", self._serial_port
            )
            return
        electricity_id = electricity_id.replace(" ", "")

        new_entities: list[EDL21Entity] = []
        for telegram in message_body.get("valList", []):
            if not (obis := telegram.get("objName")):
                continue

            if (electricity_id, obis) in self._registered_obis:
                async_dispatcher_send(
                    self._hass, SIGNAL_EDL21_TELEGRAM, electricity_id, telegram
                )
            else:
                entity_description = SENSORS.get(obis)
                if entity_description:
                    new_entities.append(
                        EDL21Entity(
                            electricity_id,
                            obis,
                            entity_description,
                            telegram,
                        )
                    )
                    self._registered_obis.add((electricity_id, obis))
                elif obis not in self._OBIS_BLACKLIST:
                    LOGGER.warning(
                        "Unhandled sensor %s detected. Please report at %s",
                        obis,
                        "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+edl21%22",
                    )
                    self._OBIS_BLACKLIST.add(obis)

        if new_entities:
            self._async_add_entities(new_entities, update_before_add=True)


class EDL21Entity(SensorEntity):
    """Entity reading values from EDL21 telegram."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, electricity_id, obis, entity_description, telegram):
        """Initialize an EDL21Entity."""
        self._electricity_id = electricity_id
        self._obis = obis
        self._telegram = telegram
        self._min_time = MIN_TIME_BETWEEN_UPDATES
        self._last_update = utcnow()
        self._async_remove_dispatcher = None
        self.entity_description = entity_description
        self._attr_unique_id = f"{electricity_id}_{obis}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._electricity_id)},
            name=DEFAULT_DEVICE_NAME,
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        @callback
        def handle_telegram(electricity_id, telegram):
            """Update attributes from last received telegram for this object."""
            if self._electricity_id != electricity_id:
                return
            if self._obis != telegram.get("objName"):
                return
            if self._telegram == telegram:
                return

            now = utcnow()
            if now - self._last_update < self._min_time:
                return

            self._telegram = telegram
            self._last_update = now
            self.async_write_ha_state()

        self._async_remove_dispatcher = async_dispatcher_connect(
            self.hass, SIGNAL_EDL21_TELEGRAM, handle_telegram
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._async_remove_dispatcher:
            self._async_remove_dispatcher()

    @property
    def native_value(self) -> str:
        """Return the value of the last received telegram."""
        return self._telegram.get("value")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if (unit := self._telegram.get("unit")) is None or unit == 0:
            return None

        return SENSOR_UNIT_MAPPING[unit]
