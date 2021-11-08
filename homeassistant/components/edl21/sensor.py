"""Support for EDL21 Smart Meters."""
from __future__ import annotations

from datetime import timedelta
import logging

from sml import SmlGetListResponse
from sml.asyncio import SmlProtocol
import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

DOMAIN = "edl21"
CONF_SERIAL_PORT = "serial_port"
ICON_POWER = "mdi:flash"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
SIGNAL_EDL21_TELEGRAM = "edl21_telegram"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_NAME, default=""): cv.string,
    },
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EDL21 sensor."""
    hass.data[DOMAIN] = EDL21(hass, config, async_add_entities)
    await hass.data[DOMAIN].connect()


class EDL21:
    """EDL21 handles telegrams sent by a compatible smart meter."""

    # OBIS format: A-B:C.D.E*F
    _OBIS_SENSOR_ENTITY_DESCRIPTIONS = {
        # A=1: Electricity
        # C=0: General purpose objects
        # D=0: Free ID-numbers for utilities
        "1-0:0.0.9*255": SensorEntityDescription(
            key="Electricity ID", name="Electricity ID"
        ),
        # D=2: Program entries
        "1-0:0.2.0*0": SensorEntityDescription(
            key="Configuration program version number",
            name="Configuration program version number",
        ),
        "1-0:0.2.0*1": SensorEntityDescription(
            key="Firmware version number", name="Firmware version number"
        ),
        # C=1: Active power +
        # D=8: Time integral 1
        # E=0: Total
        "1-0:1.8.0*255": SensorEntityDescription(
            key="Positive active energy total",
            name="Positive active energy total",
            state_class=STATE_CLASS_TOTAL_INCREASING,
            device_class=DEVICE_CLASS_ENERGY,
        ),
        # E=1: Rate 1
        "1-0:1.8.1*255": SensorEntityDescription(
            key="Positive active energy in tariff T1",
            name="Positive active energy in tariff T1",
            state_class=STATE_CLASS_TOTAL_INCREASING,
            device_class=DEVICE_CLASS_ENERGY,
        ),
        # E=2: Rate 2
        "1-0:1.8.2*255": SensorEntityDescription(
            key="Positive active energy in tariff T2",
            name="Positive active energy in tariff T2",
            state_class=STATE_CLASS_TOTAL_INCREASING,
            device_class=DEVICE_CLASS_ENERGY,
        ),
        # D=17: Time integral 7
        # E=0: Total
        "1-0:1.17.0*255": SensorEntityDescription(
            key="Last signed positive active energy total",
            name="Last signed positive active energy total",
        ),
        # C=2: Active power -
        # D=8: Time integral 1
        # E=0: Total
        "1-0:2.8.0*255": SensorEntityDescription(
            key="Negative active energy total",
            name="Negative active energy total",
            state_class=STATE_CLASS_TOTAL_INCREASING,
            device_class=DEVICE_CLASS_ENERGY,
        ),
        # E=1: Rate 1
        "1-0:2.8.1*255": SensorEntityDescription(
            key="Negative active energy in tariff T1",
            name="Negative active energy in tariff T1",
            state_class=STATE_CLASS_TOTAL_INCREASING,
            device_class=DEVICE_CLASS_ENERGY,
        ),
        # E=2: Rate 2
        "1-0:2.8.2*255": SensorEntityDescription(
            key="Negative active energy in tariff T2",
            name="Negative active energy in tariff T2",
            state_class=STATE_CLASS_TOTAL_INCREASING,
            device_class=DEVICE_CLASS_ENERGY,
        ),
        # C=14: Supply frequency
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:14.7.0*255": SensorEntityDescription(
            key="Supply frequency", name="Supply frequency"
        ),
        # C=15: Active power absolute
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:15.7.0*255": SensorEntityDescription(
            key="Absolute active instantaneous power",
            name="Absolute active instantaneous power",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_POWER,
        ),
        # C=16: Active power sum
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:16.7.0*255": SensorEntityDescription(
            key="Sum active instantaneous power",
            name="Sum active instantaneous power",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_POWER,
        ),
        # C=31: Active amperage L1
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:31.7.0*255": SensorEntityDescription(
            key="L1 active instantaneous amperage",
            name="L1 active instantaneous amperage",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_CURRENT,
        ),
        # C=32: Active voltage L1
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:32.7.0*255": SensorEntityDescription(
            key="L1 active instantaneous voltage",
            name="L1 active instantaneous voltage",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_VOLTAGE,
        ),
        # C=36: Active power L1
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:36.7.0*255": SensorEntityDescription(
            key="L1 active instantaneous power", name="L1 active instantaneous power"
        ),
        # C=51: Active amperage L2
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:51.7.0*255": SensorEntityDescription(
            key="L2 active instantaneous amperage",
            name="L2 active instantaneous amperage",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_CURRENT,
        ),
        # C=52: Active voltage L2
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:52.7.0*255": SensorEntityDescription(
            key="L2 active instantaneous voltage",
            name="L2 active instantaneous voltage",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_VOLTAGE,
        ),
        # C=56: Active power L2
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:56.7.0*255": SensorEntityDescription(
            key="L2 active instantaneous power",
            name="L2 active instantaneous power",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_POWER,
        ),
        # C=71: Active amperage L3
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:71.7.0*255": SensorEntityDescription(
            key="L3 active instantaneous amperage",
            name="L3 active instantaneous amperage",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_CURRENT,
        ),
        # C=72: Active voltage L3
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:72.7.0*255": SensorEntityDescription(
            key="L3 active instantaneous voltage",
            name="L3 active instantaneous voltage",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_VOLTAGE,
        ),
        # C=76: Active power L3
        # D=7: Instantaneous value
        # E=0: Total
        "1-0:76.7.0*255": SensorEntityDescription(
            key="L3 active instantaneous power",
            name="L3 active instantaneous power",
            state_class=STATE_CLASS_MEASUREMENT,
            device_class=DEVICE_CLASS_POWER,
        ),
        # C=81: Angles
        # D=7: Instantaneous value
        # E=4:  U(L1) x I(L1)
        # E=15: U(L2) x I(L2)
        # E=26: U(L3) x I(L3)
        "1-0:81.7.4*255": SensorEntityDescription(
            key="U(L1)/I(L1) phase angle", name="U(L1)/I(L1) phase angle"
        ),
        "1-0:81.7.15*255": SensorEntityDescription(
            key="U(L2)/I(L2) phase angle", name="U(L2)/I(L2) phase angle"
        ),
        "1-0:81.7.26*255": SensorEntityDescription(
            key="U(L3)/I(L3) phase angle", name="U(L3)/I(L3) phase angle"
        ),
        # C=96: Electricity-related service entries
        "1-0:96.1.0*255": SensorEntityDescription(
            key="Metering point ID 1", name="Metering point ID 1"
        ),
        "1-0:96.5.0*255": SensorEntityDescription(
            key="Internal operating status", name="Internal operating status"
        ),
    }
    _OBIS_BLACKLIST = {
        # C=96: Electricity-related service entries
        "1-0:96.50.1*1",  # Manufacturer specific
        "1-0:96.90.2*1",  # Manufacturer specific
        "1-0:96.90.2*2",  # Manufacturer specific
        # A=129: Manufacturer specific
        "129-129:199.130.3*255",  # Iskraemeco: Manufacturer
        "129-129:199.130.5*255",  # Iskraemeco: Public Key
    }

    def __init__(self, hass, config, async_add_entities) -> None:
        """Initialize an EDL21 object."""
        self._registered_obis: set[tuple[str, str]] = set()
        self._hass = hass
        self._async_add_entities = async_add_entities
        self._name = config[CONF_NAME]
        self._proto = SmlProtocol(config[CONF_SERIAL_PORT])
        self._proto.add_listener(self.event, ["SmlGetListResponse"])

    async def connect(self):
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

        new_entities = []
        for telegram in message_body.get("valList", []):
            if not (obis := telegram.get("objName")):
                continue

            if (electricity_id, obis) in self._registered_obis:
                async_dispatcher_send(
                    self._hass, SIGNAL_EDL21_TELEGRAM, electricity_id, telegram
                )
            else:         
                if entity_description := self._OBIS_SENSOR_ENTITY_DESCRIPTIONS.get(obis) and entity_description.name:
                    if self._name:
                        entity_description.name = (
                            f"{self._name}: {entity_description.name}"
                        )
                    new_entities.append(
                        EDL21Entity(electricity_id, obis, entity_description, telegram)
                    )
                    self._registered_obis.add((electricity_id, obis))
                elif obis not in self._OBIS_BLACKLIST:
                    _LOGGER.warning(
                        "Unhandled sensor %s detected. Please report at "
                        'https://github.com/home-assistant/core/issues?q=is%%3Aissue+label%%3A"integration%%3A+edl21"+',
                        obis,
                    )
                    self._OBIS_BLACKLIST.add(obis)

        if new_entities:
            self._hass.loop.create_task(self.add_entities(new_entities))

    async def add_entities(self, new_entities) -> None:
        """Migrate old unique IDs, then add entities to hass."""
        registry = await async_get_registry(self._hass)

        for entity in new_entities:
            old_entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, entity.old_unique_id
            )
            if old_entity_id is not None:
                _LOGGER.debug(
                    "Migrating unique_id from [%s] to [%s]",
                    entity.old_unique_id,
                    entity.unique_id,
                )
                if registry.async_get_entity_id("sensor", DOMAIN, entity.unique_id):
                    registry.async_remove(old_entity_id)
                else:
                    registry.async_update_entity(
                        old_entity_id, new_unique_id=entity.unique_id
                    )

        self._async_add_entities(new_entities, update_before_add=True)


class EDL21Entity(SensorEntity):
    """Entity reading values from EDL21 telegram."""

    def __init__(self, electricity_id, obis, entity_description, telegram):
        """Initialize an EDL21Entity."""
        self._electricity_id = electricity_id
        self._obis = obis
        self._unique_id = f"{electricity_id}_{obis}"
        self._telegram = telegram
        self._min_time = MIN_TIME_BETWEEN_UPDATES
        self._last_update = utcnow()
        self._state_attrs = {
            "status": "status",
            "valTime": "val_time",
            "scaler": "scaler",
            "valueSignature": "value_signature",
        }
        self._async_remove_dispatcher = None
        self.entity_description = entity_description

    async def async_added_to_hass(self):
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

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        if self._async_remove_dispatcher:
            self._async_remove_dispatcher()

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def old_unique_id(self) -> str:
        """Return a less unique ID as used in the first version of edl21."""
        return self._obis

    @property
    def native_value(self) -> str:
        """Return the value of the last received telegram."""
        return self._telegram.get("value")

    @property
    def extra_state_attributes(self):
        """Enumerate supported attributes."""
        return {
            self._state_attrs[k]: v
            for k, v in self._telegram.items()
            if k in self._state_attrs
        }

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._telegram.get("unit")

    @property
    def icon(self):
        """Return an icon."""
        return ICON_POWER
