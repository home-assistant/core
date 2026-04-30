"""Support for consuming values for the Volkszaehler API."""

from __future__ import annotations

from datetime import timedelta
import logging

from volkszaehler import Volkszaehler
from volkszaehler.exceptions import VolkszaehlerApiConnectionError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_UUID,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="average",
        name="Average",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:power-off",
    ),
    SensorEntityDescription(
        key="consumption",
        name="Consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:power-plug",
    ),
    SensorEntityDescription(
        key="max",
        name="Max",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:arrow-up",
    ),
    SensorEntityDescription(
        key="min",
        name="Min",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        icon="mdi:arrow-down",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import Volkszaehler sensor YAML config into config flow."""
    data = {
        CONF_HOST: config.get(CONF_HOST),
        CONF_NAME: config.get(CONF_NAME),
        CONF_PORT: config.get(CONF_PORT),
        CONF_UUID: config.get(CONF_UUID),
    }
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=data,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Volkszaehler sensors from a config entry."""
    data = entry.data
    host: str = data[CONF_HOST]
    name: str = data[CONF_NAME]
    port: int = data[CONF_PORT]
    uuid: str = data[CONF_UUID]
    conditions = SENSOR_KEYS

    session = async_get_clientsession(hass)
    vz_api = VolkszaehlerData(Volkszaehler(session, uuid, host=host, port=port))
    await vz_api.async_update()

    if vz_api.api.data is None:
        raise PlatformNotReady
    entities = [
        VolkszaehlerSensor(vz_api, name, description)
        for description in SENSOR_TYPES
        if description.key in conditions
    ]

    async_add_entities(entities, True)


class VolkszaehlerSensor(SensorEntity):
    """Implementation of a Volkszaehler sensor."""

    def __init__(
        self, vz_api: VolkszaehlerData, name: str, description: SensorEntityDescription
    ) -> None:
        """Initialize the Volkszaehler sensor."""
        self.entity_description = description
        self.vz_api = vz_api

        self._attr_name = f"{name} {description.name}"

    @property
    def available(self) -> bool:
        """Could the device be accessed during the last update call."""
        return self.vz_api.available

    async def async_update(self) -> None:
        """Get the latest data from REST API."""
        await self.vz_api.async_update()

        if self.vz_api.api.data is not None:
            self._attr_native_value = round(
                getattr(self.vz_api.api, self.entity_description.key), 2
            )


class VolkszaehlerData:
    """The class for handling the data retrieval from the Volkszaehler API."""

    def __init__(self, api: Volkszaehler) -> None:
        """Initialize the data object."""
        self.api = api
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Get the latest data from the Volkszaehler REST API."""

        try:
            await self.api.get_data()
            self.available = True
        except VolkszaehlerApiConnectionError:
            _LOGGER.error("Unable to fetch data from the Volkszaehler API")
            self.available = False
