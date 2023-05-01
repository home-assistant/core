"""Support for EDL21 Smart Meters."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from sml import SmlGetListResponse
from sml.asyncio import SmlProtocol
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    DEGREE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utcnow

from .const import (
    CONF_SERIAL_PORT,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    LOGGER,
    SIGNAL_EDL21_TELEGRAM,
)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_NAME, default=""): cv.string,
    },
)

# OBIS format: A-B:C.D.E*F
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    # A=1: Electricity
    # C=0: General purpose objects
    # D=0: Free ID-numbers for utilities
    # E=0 Ownership ID
    SensorEntityDescription(
        key="1-0:0.0.0*255",
        name="Ownership ID",
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    # E=9: Electrity ID
    SensorEntityDescription(
        key="1-0:0.0.9*255", name="Electricity ID", icon="mdi:flash"
    ),
    # D=2: Program entries
    SensorEntityDescription(
        key="1-0:0.2.0*0", name="Configuration program version number", icon="mdi:flash"
    ),
    SensorEntityDescription(
        key="1-0:0.2.0*1", name="Firmware version number", icon="mdi:flash"
    ),
    # C=1: Active power +
    # D=8: Time integral 1
    # E=0: Total
    SensorEntityDescription(
        key="1-0:1.8.0*255",
        name="Positive active energy total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # E=1: Rate 1
    SensorEntityDescription(
        key="1-0:1.8.1*255",
        name="Positive active energy in tariff T1",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # E=2: Rate 2
    SensorEntityDescription(
        key="1-0:1.8.2*255",
        name="Positive active energy in tariff T2",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # D=17: Time integral 7
    # E=0: Total
    SensorEntityDescription(
        key="1-0:1.17.0*255",
        name="Last signed positive active energy total",
    ),
    # C=2: Active power -
    # D=8: Time integral 1
    # E=0: Total
    SensorEntityDescription(
        key="1-0:2.8.0*255",
        name="Negative active energy total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # E=1: Rate 1
    SensorEntityDescription(
        key="1-0:2.8.1*255",
        name="Negative active energy in tariff T1",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # E=2: Rate 2
    SensorEntityDescription(
        key="1-0:2.8.2*255",
        name="Negative active energy in tariff T2",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    # C=14: Supply frequency
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:14.7.0*255", name="Supply frequency", icon="mdi:sine-wave"
    ),
    # C=15: Active power absolute
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:15.7.0*255",
        name="Absolute active instantaneous power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=16: Active power sum
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:16.7.0*255",
        name="Sum active instantaneous power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=31: Active amperage L1
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:31.7.0*255",
        name="L1 active instantaneous amperage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    # C=32: Active voltage L1
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:32.7.0*255",
        name="L1 active instantaneous voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # C=36: Active power L1
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:36.7.0*255",
        name="L1 active instantaneous power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=51: Active amperage L2
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:51.7.0*255",
        name="L2 active instantaneous amperage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    # C=52: Active voltage L2
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:52.7.0*255",
        name="L2 active instantaneous voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # C=56: Active power L2
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:56.7.0*255",
        name="L2 active instantaneous power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    # C=71: Active amperage L3
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:71.7.0*255",
        name="L3 active instantaneous amperage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    # C=72: Active voltage L3
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:72.7.0*255",
        name="L3 active instantaneous voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # C=76: Active power L3
    # D=7: Instantaneous value
    # E=0: Total
    SensorEntityDescription(
        key="1-0:76.7.0*255",
        name="L3 active instantaneous power",
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
        key="1-0:81.7.1*255", name="U(L2)/U(L1) phase angle", icon="mdi:sine-wave"
    ),
    SensorEntityDescription(
        key="1-0:81.7.2*255", name="U(L3)/U(L1) phase angle", icon="mdi:sine-wave"
    ),
    SensorEntityDescription(
        key="1-0:81.7.4*255", name="U(L1)/I(L1) phase angle", icon="mdi:sine-wave"
    ),
    SensorEntityDescription(
        key="1-0:81.7.15*255", name="U(L2)/I(L2) phase angle", icon="mdi:sine-wave"
    ),
    SensorEntityDescription(
        key="1-0:81.7.26*255", name="U(L3)/I(L3) phase angle", icon="mdi:sine-wave"
    ),
    # C=96: Electricity-related service entries
    SensorEntityDescription(
        key="1-0:96.1.0*255", name="Metering point ID 1", icon="mdi:flash"
    ),
    SensorEntityDescription(
        key="1-0:96.5.0*255", name="Internal operating status", icon="mdi:flash"
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up EDL21 sensors via configuration.yaml and show deprecation warning."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.6.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


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
        self._name = config.get(CONF_NAME)
        self._proto = SmlProtocol(config[CONF_SERIAL_PORT])
        self._proto.add_listener(self.event, ["SmlGetListResponse"])

    async def connect(self) -> None:
        """Connect to an EDL21 reader."""
        await self._proto.connect(self._hass.loop)

    def event(self, message_body) -> None:
        """Handle events from pysml."""
        assert isinstance(message_body, SmlGetListResponse)

        electricity_id = None
        for telegram in message_body.get("valList", []):
            if telegram.get("objName") in ("1-0:0.0.9*255", "1-0:96.1.0*255"):
                electricity_id = telegram.get("value")
                break

        if electricity_id is None:
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
                if entity_description and entity_description.name:
                    # self._name is only used for backwards YAML compatibility
                    # This needs to be cleaned up when YAML support is removed
                    device_name = self._name or DEFAULT_DEVICE_NAME
                    new_entities.append(
                        EDL21Entity(
                            electricity_id,
                            obis,
                            device_name,
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

    def __init__(self, electricity_id, obis, device_name, entity_description, telegram):
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
            name=device_name,
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
