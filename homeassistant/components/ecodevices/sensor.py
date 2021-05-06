"""Support for the GCE Eco-Devices."""
import logging

from homeassistant.const import DEVICE_CLASS_POWER
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_C1_DEVICE_CLASS,
    CONF_C1_ENABLED,
    CONF_C1_UNIT_OF_MEASUREMENT,
    CONF_C2_DEVICE_CLASS,
    CONF_C2_ENABLED,
    CONF_C2_UNIT_OF_MEASUREMENT,
    CONF_T1_ENABLED,
    CONF_T1_UNIT_OF_MEASUREMENT,
    CONF_T2_ENABLED,
    CONF_T2_UNIT_OF_MEASUREMENT,
    CONFIG,
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
    config = data[CONFIG]

    entities = []

    if config.get(CONF_T1_ENABLED):
        _LOGGER.debug("Add the teleinfo 1 entity")
        entities.append(
            T1EdDevice(
                controller,
                coordinator,
                "t1",
                DEFAULT_T1_NAME,
                config.get(CONF_T1_UNIT_OF_MEASUREMENT),
                DEVICE_CLASS_POWER,
                "mdi:flash",
            )
        )
    if config.get(CONF_T2_ENABLED):
        _LOGGER.debug("Add the teleinfo 2 entity")
        entities.append(
            T2EdDevice(
                controller,
                coordinator,
                "t2",
                DEFAULT_T2_NAME,
                config.get(CONF_T2_UNIT_OF_MEASUREMENT),
                DEVICE_CLASS_POWER,
                "mdi:flash",
            )
        )
    if config.get(CONF_C1_ENABLED):
        _LOGGER.debug("Add the meter 1 entity")
        entities.append(
            C1EdDevice(
                controller,
                coordinator,
                "c1",
                DEFAULT_C1_NAME,
                config.get(CONF_C1_UNIT_OF_MEASUREMENT),
                config.get(CONF_C1_DEVICE_CLASS),
            )
        )
    if config.get(CONF_C2_ENABLED):
        _LOGGER.debug("Add the meter 2 entity")
        entities.append(
            C2EdDevice(
                controller,
                coordinator,
                "c2",
                DEFAULT_C2_NAME,
                config.get(CONF_C2_UNIT_OF_MEASUREMENT),
                config.get(CONF_C2_DEVICE_CLASS),
            )
        )

    if entities:
        async_add_entities(entities, True)


class EdDevice(CoordinatorEntity):
    """Representation of a generic Eco-Devices sensor."""

    def __init__(
        self,
        controller,
        coordinator,
        input_name,
        name,
        unit,
        device_class,
        icon=None,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.controller = controller
        self._input_name = input_name
        self._name = name
        self._unit = unit
        self._device_class = device_class
        self._icon = icon
        self._state = None

    @property
    def device_info(self):
        """Return device information identifier."""
        return {
            "identifiers": {(DOMAIN, self.controller.host)},
            "via_device": (DOMAIN, self.controller.host),
        }

    @property
    def unique_id(self):
        """Return an unique id."""
        return "_".join(
            [
                DOMAIN,
                self.controller.host,
                "sensor",
                self._input_name,
            ]
        )

    @property
    def device_class(self):
        """Return the device_class."""
        return self._device_class

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement if specified."""
        return self._unit

    @property
    def icon(self):
        """Return the icon if specified."""
        return self._icon


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
