"""Support for the GCE Eco-Devices."""
import logging

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_C1_DEVICE_CLASS,
    CONF_C1_ENABLED,
    CONF_C1_NAME,
    CONF_C1_UNIT_OF_MEASUREMENT,
    CONF_C2_DEVICE_CLASS,
    CONF_C2_ENABLED,
    CONF_C2_NAME,
    CONF_C2_UNIT_OF_MEASUREMENT,
    CONF_T1_ENABLED,
    CONF_T1_NAME,
    CONF_T1_UNIT_OF_MEASUREMENT,
    CONF_T2_ENABLED,
    CONF_T2_NAME,
    CONF_T2_UNIT_OF_MEASUREMENT,
    CONFIG,
    CONTROLLER,
    COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the GCE Eco-Devices platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    controller = data[CONTROLLER]
    coordinator = data[COORDINATOR]
    config = data[CONFIG]

    entities = []

    if config.get(CONF_T1_ENABLED):
        _LOGGER.debug("Add the teleinfo 1 entity")
        entities.append(
            T1EdDevice(
                controller,
                coordinator,
                input_name="t1",
                name=config.get(CONF_T1_NAME),
                unit=config.get(CONF_T1_UNIT_OF_MEASUREMENT),
                device_class="power",
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:flash",
            )
        )
        entities.append(
            T1TotalEdDevice(
                controller,
                coordinator,
                input_name="t1_total",
                name=config.get(CONF_T1_NAME) + " Total",
                unit="Wh",
                device_class="energy",
                state_class=STATE_CLASS_TOTAL_INCREASING,
                icon="mdi:flash",
            )
        )
    if config.get(CONF_T2_ENABLED):
        _LOGGER.debug("Add the teleinfo 2 entity")
        entities.append(
            T2EdDevice(
                controller,
                coordinator,
                input_name="t2",
                name=config.get(CONF_T2_NAME),
                unit=config.get(CONF_T2_UNIT_OF_MEASUREMENT),
                device_class="power",
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:flash",
            )
        )
        entities.append(
            T2TotalEdDevice(
                controller,
                coordinator,
                input_name="t2_total",
                name=config.get(CONF_T2_NAME) + " Total",
                unit="Wh",
                device_class="energy",
                state_class=STATE_CLASS_TOTAL_INCREASING,
                icon="mdi:flash",
            )
        )
    if config.get(CONF_C1_ENABLED):
        _LOGGER.debug("Add the meter 1 entity")
        entities.append(
            C1EdDevice(
                controller,
                coordinator,
                input_name="c1",
                name=config.get(CONF_C1_NAME),
                unit=config.get(CONF_C1_UNIT_OF_MEASUREMENT),
                device_class=config.get(CONF_C1_DEVICE_CLASS),
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:counter",
            )
        )
        entities.append(
            C2TotalEdDevice(
                controller,
                coordinator,
                input_name="c1_total",
                name=config.get(CONF_C1_NAME) + " Total",
                unit=config.get(CONF_C1_UNIT_OF_MEASUREMENT),
                device_class=config.get(CONF_C1_DEVICE_CLASS),
                state_class=STATE_CLASS_TOTAL_INCREASING,
                icon="mdi:counter",
            )
        )
    if config.get(CONF_C2_ENABLED):
        _LOGGER.debug("Add the meter 2 entity")
        entities.append(
            C2EdDevice(
                controller,
                coordinator,
                input_name="c2",
                name=config.get(CONF_C2_NAME),
                unit=config.get(CONF_C2_UNIT_OF_MEASUREMENT),
                device_class=config.get(CONF_C2_DEVICE_CLASS),
                state_class=STATE_CLASS_MEASUREMENT,
                icon="mdi:counter",
            )
        )
        entities.append(
            C2TotalEdDevice(
                controller,
                coordinator,
                input_name="c2_total",
                name=config.get(CONF_C2_NAME) + " Total",
                unit=config.get(CONF_C2_UNIT_OF_MEASUREMENT),
                device_class=config.get(CONF_C2_DEVICE_CLASS),
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
        self._attr_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_unique_id = "_".join(
            [
                DOMAIN,
                self.controller.host,
                "sensor",
                self._input_name,
            ]
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.controller.host)},
            "via_device": (DOMAIN, self.controller.host),
        }

        self._state = None


class T1EdDevice(EdDevice):
    """Initialize the T1 sensor."""

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data["T1_PAPP"]

    @property
    def state_attributes(self):
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
    def state(self):
        """Return the state."""
        return self.coordinator.data["T1_BASE"]


class T2EdDevice(EdDevice):
    """Initialize the T2 sensor."""

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data["T2_PAPP"]

    @property
    def state_attributes(self):
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
    def state(self):
        """Return the state."""
        return self.coordinator.data["T2_BASE"]


class C1EdDevice(EdDevice):
    """Initialize the C1 sensor."""

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data["c0day"]

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "total": self.coordinator.data["count0"],
                "fuel": self.coordinator.data["c0_fuel"],
            }


class C1TotalEdDevice(EdDevice):
    """Initialize the C1 sensor."""

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data["count0"]


class C2EdDevice(EdDevice):
    """Initialize the C2 sensor."""

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data["c1day"]

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data:
            return {
                "total": self.coordinator.data["count1"],
                "fuel": self.coordinator.data["c1_fuel"],
            }


class C2TotalEdDevice(EdDevice):
    """Initialize the C1 sensor."""

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data["count1"]
