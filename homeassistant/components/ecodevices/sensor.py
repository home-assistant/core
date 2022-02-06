"""Support for the GCE Eco-Devices."""
import logging

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_C1_DEVICE_CLASS,
    CONF_C1_ENABLED,
    CONF_C1_TOTAL_UNIT_OF_MEASUREMENT,
    CONF_C1_UNIT_OF_MEASUREMENT,
    CONF_C2_DEVICE_CLASS,
    CONF_C2_ENABLED,
    CONF_C2_TOTAL_UNIT_OF_MEASUREMENT,
    CONF_C2_UNIT_OF_MEASUREMENT,
    CONF_T1_ENABLED,
    CONF_T1_HCHP,
    CONF_T2_ENABLED,
    CONF_T2_HCHP,
    CONTROLLER,
    COORDINATOR,
    DEFAULT_C1_NAME,
    DEFAULT_C2_NAME,
    DEFAULT_T1_NAME,
    DEFAULT_T2_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the GCE Eco-Devices platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    controller = data[CONTROLLER]
    coordinator = data[COORDINATOR]
    config = config_entry.data
    options = config_entry.options

    t1_enabled = options.get(CONF_T1_ENABLED, config.get(CONF_T1_ENABLED))
    t1_hchp = options.get(CONF_T1_HCHP, config.get(CONF_T1_HCHP))
    t2_enabled = options.get(CONF_T2_ENABLED, config.get(CONF_T2_ENABLED))
    t2_hchp = options.get(CONF_T2_HCHP, config.get(CONF_T2_HCHP))
    c1_enabled = options.get(CONF_C1_ENABLED, config.get(CONF_C1_ENABLED))
    c2_enabled = options.get(CONF_C2_ENABLED, config.get(CONF_C2_ENABLED))

    entities = []

    if t1_enabled:
        _LOGGER.debug("Add the teleinfo 1 entities")
        entities.append(
            T1EdDevice(
                controller,
                coordinator,
                input_name="t1",
                name=DEFAULT_T1_NAME,
                unit=POWER_WATT,
                device_class=DEVICE_CLASS_POWER,
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:flash",
            )
        )
        if t1_hchp:
            entities.append(
                T1TotalHchpEdDevice(
                    controller,
                    coordinator,
                    input_name="t1_total",
                    name=DEFAULT_T1_NAME + " Total",
                    unit=ENERGY_WATT_HOUR,
                    device_class=DEVICE_CLASS_ENERGY,
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    icon="mdi:flash",
                )
            )
            entities.append(
                T1TotalHcEdDevice(
                    controller,
                    coordinator,
                    input_name="t1_total_hc",
                    name=DEFAULT_T1_NAME + " HC Total",
                    unit=ENERGY_WATT_HOUR,
                    device_class=DEVICE_CLASS_ENERGY,
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    icon="mdi:flash",
                )
            )
            entities.append(
                T1TotalHpEdDevice(
                    controller,
                    coordinator,
                    input_name="t1_total_hp",
                    name=DEFAULT_T1_NAME + " HP Total",
                    unit=ENERGY_WATT_HOUR,
                    device_class=DEVICE_CLASS_ENERGY,
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    icon="mdi:flash",
                )
            )
        else:
            entities.append(
                T1TotalEdDevice(
                    controller,
                    coordinator,
                    input_name="t1_total",
                    name=DEFAULT_T1_NAME + " Total",
                    unit=ENERGY_WATT_HOUR,
                    device_class=DEVICE_CLASS_ENERGY,
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    icon="mdi:flash",
                )
            )
    if t2_enabled:
        _LOGGER.debug("Add the teleinfo 2 entities")
        entities.append(
            T2EdDevice(
                controller,
                coordinator,
                input_name="t2",
                name=DEFAULT_T2_NAME,
                unit=POWER_WATT,
                device_class=DEVICE_CLASS_POWER,
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:flash",
            )
        )
        if t2_hchp:
            entities.append(
                T2TotalHchpEdDevice(
                    controller,
                    coordinator,
                    input_name="t2_total",
                    name=DEFAULT_T2_NAME + " Total",
                    unit=ENERGY_WATT_HOUR,
                    device_class=DEVICE_CLASS_ENERGY,
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    icon="mdi:flash",
                )
            )
            entities.append(
                T2TotalHcEdDevice(
                    controller,
                    coordinator,
                    input_name="t2_total_hc",
                    name=DEFAULT_T2_NAME + " HC Total",
                    unit=ENERGY_WATT_HOUR,
                    device_class=DEVICE_CLASS_ENERGY,
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    icon="mdi:flash",
                )
            )
            entities.append(
                T2TotalHpEdDevice(
                    controller,
                    coordinator,
                    input_name="t2_total_hp",
                    name=DEFAULT_T2_NAME + " HP Total",
                    unit=ENERGY_WATT_HOUR,
                    device_class=DEVICE_CLASS_ENERGY,
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    icon="mdi:flash",
                )
            )
        else:
            entities.append(
                T2TotalEdDevice(
                    controller,
                    coordinator,
                    input_name="t2_total",
                    name=DEFAULT_T2_NAME + " Total",
                    unit=ENERGY_WATT_HOUR,
                    device_class="energy",
                    state_class=STATE_CLASS_TOTAL_INCREASING,
                    icon="mdi:flash",
                )
            )
    if c1_enabled:
        _LOGGER.debug("Add the meter 1 entities")
        entities.append(
            C1EdDevice(
                controller,
                coordinator,
                input_name="c1",
                name=DEFAULT_C1_NAME,
                unit=options.get(
                    CONF_C1_UNIT_OF_MEASUREMENT, config.get(CONF_C1_UNIT_OF_MEASUREMENT)
                ),
                device_class=options.get(
                    CONF_C1_DEVICE_CLASS, config.get(CONF_C1_DEVICE_CLASS)
                ),
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:counter",
            )
        )
        entities.append(
            C1DailyEdDevice(
                controller,
                coordinator,
                input_name="c1_daily",
                name=DEFAULT_C1_NAME + " Daily",
                unit=options.get(
                    CONF_C1_UNIT_OF_MEASUREMENT, config.get(CONF_C1_UNIT_OF_MEASUREMENT)
                ),
                device_class=options.get(
                    CONF_C1_DEVICE_CLASS, config.get(CONF_C1_DEVICE_CLASS)
                ),
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:counter",
            )
        )
        entities.append(
            C1TotalEdDevice(
                controller,
                coordinator,
                input_name="c1_total",
                name=DEFAULT_C1_NAME + " Total",
                unit=options.get(
                    CONF_C1_TOTAL_UNIT_OF_MEASUREMENT,
                    config.get(
                        CONF_C1_TOTAL_UNIT_OF_MEASUREMENT,
                        config.get(CONF_C1_UNIT_OF_MEASUREMENT),
                    ),
                ),
                device_class=options.get(
                    CONF_C1_DEVICE_CLASS, config.get(CONF_C1_DEVICE_CLASS)
                ),
                state_class=STATE_CLASS_TOTAL_INCREASING,
                icon="mdi:counter",
            )
        )
    if c2_enabled:
        _LOGGER.debug("Add the meter 2 entities")
        entities.append(
            C2EdDevice(
                controller,
                coordinator,
                input_name="c2",
                name=DEFAULT_C2_NAME,
                unit=config.get(CONF_C2_UNIT_OF_MEASUREMENT),
                device_class=options.get(
                    CONF_C2_DEVICE_CLASS, config.get(CONF_C2_DEVICE_CLASS)
                ),
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:counter",
            )
        )
        entities.append(
            C2DailyEdDevice(
                controller,
                coordinator,
                input_name="c2_daily",
                name=DEFAULT_C2_NAME + " Daily",
                unit=options.get(
                    CONF_C2_UNIT_OF_MEASUREMENT, config.get(CONF_C2_UNIT_OF_MEASUREMENT)
                ),
                device_class=options.get(
                    CONF_C2_DEVICE_CLASS, config.get(CONF_C2_DEVICE_CLASS)
                ),
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:counter",
            )
        )
        entities.append(
            C2TotalEdDevice(
                controller,
                coordinator,
                input_name="c2_total",
                name=DEFAULT_C2_NAME + " Total",
                unit=options.get(
                    CONF_C2_TOTAL_UNIT_OF_MEASUREMENT,
                    config.get(
                        CONF_C2_TOTAL_UNIT_OF_MEASUREMENT,
                        config.get(CONF_C1_UNIT_OF_MEASUREMENT),
                    ),
                ),
                device_class=options.get(
                    CONF_C2_DEVICE_CLASS, config.get(CONF_C2_DEVICE_CLASS)
                ),
                state_class=STATE_CLASS_TOTAL_INCREASING,
                icon="mdi:counter",
            )
        )

    if entities:
        async_add_entities(entities)


class EdDevice(CoordinatorEntity, SensorEntity):
    """Representation of a generic Eco-Devices sensor."""

    def __init__(
        self,
        controller,
        coordinator,
        input_name,
        name,
        unit,
        device_class,
        state_class,
        icon,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.controller = controller
        self._input_name = input_name

        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_unique_id = slugify(
            "_".join(
                [
                    DOMAIN,
                    self.controller.mac_address,
                    "sensor",
                    self._input_name,
                ]
            )
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.controller.mac_address)},
            "via_device": (DOMAIN, self.controller.mac_address),
        }

        self._state = None


class T1EdDevice(EdDevice):
    """Initialize the T1 sensor."""

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data["T1_PAPP"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "type_heures": self.coordinator.data.get("T1_PTEC"),
                "souscription": self.coordinator.data.get("T1_ISOUSC"),
                "intensite_max": self.coordinator.data.get("T1_IMAX"),
                "intensite_max_ph1": self.coordinator.data.get("T1_IMAX1"),
                "intensite_max_ph2": self.coordinator.data.get("T1_IMAX2"),
                "intensite_max_ph3": self.coordinator.data.get("T1_IMAX3"),
                "intensite_now": self.coordinator.data.get("T1_IINST"),
                "intensite_now_ph1": self.coordinator.data.get("T1_IINST1"),
                "intensite_now_ph2": self.coordinator.data.get("T1_IINST2"),
                "intensite_now_ph3": self.coordinator.data.get("T1_IINST3"),
                "numero_compteur": self.coordinator.data.get("T1_ADCO"),
                "option_tarifaire": self.coordinator.data.get("T1_OPTARIF"),
                "index_base": self.coordinator.data.get("T1_BASE"),
                "index_heures_creuses": self.coordinator.data.get("T1_HCHC"),
                "index_heures_pleines": self.coordinator.data.get("T1_HCHP"),
                "index_heures_normales": self.coordinator.data.get("T1_EJPHN"),
                "index_heures_pointes": self.coordinator.data.get("T1_EJPHPM"),
                "preavis_heures_pointes": self.coordinator.data.get("T1_PEJP"),
                "groupe_horaire": self.coordinator.data.get("T1_HHPHC"),
                "etat": self.coordinator.data.get("T1_MOTDETAT"),
            }


class T1TotalEdDevice(EdDevice):
    """Initialize the T1 Total sensor."""

    @property
    def native_value(self):
        """Return the total value if it's greater than 0."""
        value = float(self.coordinator.data["T1_BASE"])
        if value > 0:
            return value


class T1TotalHchpEdDevice(EdDevice):
    """Initialize the T1 HCHP Total sensor."""

    @property
    def native_value(self):
        """Return the total value if it's greater than 0."""
        value_hc = float(self.coordinator.data["T1_HCHC"])
        value_hp = float(self.coordinator.data["T1_HCHP"])
        value = value_hc + value_hp
        if value > 0:
            return value


class T1TotalHcEdDevice(EdDevice):
    """Initialize the T1 HC Total sensor."""

    @property
    def native_value(self):
        """Return the total value if it's greater than 0."""
        value = float(self.coordinator.data["T1_HCHC"])
        if value > 0:
            return value


class T1TotalHpEdDevice(EdDevice):
    """Initialize the T1 HP Total sensor."""

    @property
    def native_value(self):
        """Return the total value if it's greater than 0."""
        value = float(self.coordinator.data["T1_HCHP"])
        if value > 0:
            return value


class T2EdDevice(EdDevice):
    """Initialize the T2 sensor."""

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data["T2_PAPP"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "type_heures": self.coordinator.data.get("T2_PTEC"),
                "souscription": self.coordinator.data.get("T2_ISOUSC"),
                "intensite_max": self.coordinator.data.get("T2_IMAX"),
                "intensite_max_ph1": self.coordinator.data.get("T2_IMAX1"),
                "intensite_max_ph2": self.coordinator.data.get("T2_IMAX2"),
                "intensite_max_ph3": self.coordinator.data.get("T2_IMAX3"),
                "intensite_now": self.coordinator.data.get("T2_IINST"),
                "intensite_now_ph1": self.coordinator.data.get("T2_IINST1"),
                "intensite_now_ph2": self.coordinator.data.get("T2_IINST2"),
                "intensite_now_ph3": self.coordinator.data.get("T2_IINST3"),
                "numero_compteur": self.coordinator.data.get("T2_ADCO"),
                "option_tarifaire": self.coordinator.data.get("T2_OPTARIF"),
                "index_base": self.coordinator.data.get("T2_BASE"),
                "index_heures_creuses": self.coordinator.data.get("T2_HCHC"),
                "index_heures_pleines": self.coordinator.data.get("T2_HCHP"),
                "index_heures_normales": self.coordinator.data.get("T2_EJPHN"),
                "index_heures_pointes": self.coordinator.data.get("T2_EJPHPM"),
                "preavis_heures_pointes": self.coordinator.data.get("T2_PEJP"),
                "groupe_horaire": self.coordinator.data.get("T2_HHPHC"),
                "etat": self.coordinator.data.get("T2_MOTDETAT"),
            }


class T2TotalEdDevice(EdDevice):
    """Initialize the T1 Total sensor."""

    @property
    def native_value(self):
        """Return the total value if it's greater than 0."""
        value = float(self.coordinator.data["T2_BASE"])
        if value > 0:
            return value


class T2TotalHchpEdDevice(EdDevice):
    """Initialize the T2 HCHP Total sensor."""

    @property
    def native_value(self):
        """Return the total value if it's greater than 0."""
        value_hc = float(self.coordinator.data["T2_HCHC"])
        value_hp = float(self.coordinator.data["T2_HCHP"])
        value = value_hc + value_hp
        if value > 0:
            return value


class T2TotalHcEdDevice(EdDevice):
    """Initialize the T2 HC Total sensor."""

    @property
    def native_value(self):
        """Return the total value if it's greater than 0."""
        value = float(self.coordinator.data["T2_HCHC"])
        if value > 0:
            return value


class T2TotalHpEdDevice(EdDevice):
    """Initialize the T2 HP Total sensor."""

    @property
    def native_value(self):
        """Return the total value if it's greater than 0."""
        value = float(self.coordinator.data["T2_HCHP"])
        if value > 0:
            return value


class C1EdDevice(EdDevice):
    """Initialize the C1 sensor."""

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data["meter2"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "total": self.coordinator.data["count0"],
                "fuel": self.coordinator.data["c0_fuel"],
            }


class C1DailyEdDevice(EdDevice):
    """Initialize the C1 daily sensor."""

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data["c0day"]


class C1TotalEdDevice(EdDevice):
    """Initialize the C1 total sensor."""

    @property
    def native_value(self) -> float:
        """Return the total value if it's greater than 0."""
        value = float(self.coordinator.data["count0"])
        if value > 0:
            return value / 1000
        raise EcoDevicesIncorrectValueError("Total value not greater than 0.")


class C2EdDevice(EdDevice):
    """Initialize the C2 sensor."""

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data["meter3"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "total": self.coordinator.data["count1"],
                "fuel": self.coordinator.data["c1_fuel"],
            }


class C2DailyEdDevice(EdDevice):
    """Initialize the C2 daily sensor."""

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data["c1day"]


class C2TotalEdDevice(EdDevice):
    """Initialize the C2 total sensor."""

    @property
    def native_value(self) -> float:
        """Return the total value if it's greater than 0."""
        value = float(self.coordinator.data["count1"])
        if value > 0:
            return value / 1000
        raise EcoDevicesIncorrectValueError("Total value not greater than 0.")


class EcoDevicesIncorrectValueError(Exception):
    """Exception to indicate that the Eco-Device return an incorrect value."""
