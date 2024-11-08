"""Sensor for Volkszaehler."""

from __future__ import annotations

import logging

from volkszaehler import Volkszaehler

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_FROM,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PORT,
    CONF_SCANINTERVAL,
    CONF_TO,
    CONF_UUID,
    DEFAULT_MONITORED_CONDITIONS,
    DEFAULT_NAME,
    DEFAULT_SCANINTERVAL,
    DOMAIN,
)
from .coordinator import VolkszaehlerCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "average": SensorEntityDescription(
        key="average",
        name="Average",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:power-off",
    ),
    "consumption": SensorEntityDescription(
        key="consumption",
        name="Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        icon="mdi:power-plug",
    ),
    "max": SensorEntityDescription(
        key="max",
        name="Max",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:arrow-up",
    ),
    "min": SensorEntityDescription(
        key="min",
        name="Min",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:arrow-down",
    ),
    "last": SensorEntityDescription(
        key="last",
        name="Last",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:arrow-down",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Volkszaehler sensors from a config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    uuid = config_entry.data[CONF_UUID]
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
    monitored_conditions = config_entry.options.get(
        CONF_MONITORED_CONDITIONS, DEFAULT_MONITORED_CONDITIONS
    )
    param_from = config_entry.options.get(CONF_FROM)
    param_to = config_entry.options.get(CONF_TO)
    scaninterval = config_entry.options.get(CONF_SCANINTERVAL, DEFAULT_SCANINTERVAL)

    _LOGGER.debug(
        "Volkszaehler Setup: host=%s, port=%s, uuid=%s, from=%s, to=%s, scaninterval=%s",
        host,
        port,
        uuid,
        param_from,
        param_to,
        scaninterval,
    )

    session = async_get_clientsession(hass)
    vz_api = Volkszaehler(
        session,
        uuid,
        host=host,
        port=port,
        param_from=param_from,
        param_to=param_to,
    )

    coordinator = VolkszaehlerCoordinator(
        hass,
        vz_api,
        scaninterval,
    )

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    entities = [
        VolkszaehlerSensor(coordinator, name, SENSOR_TYPES[condition], uuid)
        for condition in monitored_conditions
        if condition in SENSOR_TYPES
    ]
    async_add_entities(entities, update_before_add=True)


class VolkszaehlerSensor(CoordinatorEntity[VolkszaehlerCoordinator], SensorEntity):
    """Representation of a Volkszaehler sensor."""

    def __init__(
        self,
        coordinator: VolkszaehlerCoordinator,
        name: str,
        description: SensorEntityDescription,
        uuid: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{DOMAIN}_{name}_{uuid}_{description.key}"
        self._attr_icon = description.icon

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        value = getattr(self.coordinator.api, self.entity_description.key, None)
        if value is not None:
            try:
                return round(float(value), 2)
            except (ValueError, TypeError) as e:
                _LOGGER.error(
                    "Fehler beim Konvertieren des Wertes für %s: %s",
                    self.entity_description.key,
                    e,
                )
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success
