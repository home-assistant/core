"""Support for monitoring pyLoad."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum
import logging
from time import monotonic

from pyloadapi import (
    CannotConnect,
    InvalidAuth,
    ParserError,
    PyLoadAPI,
    StatusServerResponse,
)
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    UnitOfDataRate,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import PyLoadConfigEntry
from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN, ISSUE_PLACEHOLDER

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=15)


class PyLoadSensorEntity(StrEnum):
    """pyLoad Sensor Entities."""

    SPEED = "speed"


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=PyLoadSensorEntity.SPEED,
        name="Speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=1,
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["speed"]): vol.All(
            cv.ensure_list, [vol.In(PyLoadSensorEntity)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import config from yaml."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    _LOGGER.debug(result)
    if (
        result.get("type") == FlowResultType.CREATE_ENTRY
        or result.get("reason") == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2025.2.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "pyLoad",
            },
        )
    elif error := result.get("reason"):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{error}",
            breaks_in_ha_version="2025.2.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{error}",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PyLoadConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the pyLoad sensors."""

    pyloadapi = entry.runtime_data

    async_add_entities(
        (
            PyLoadSensor(
                api=pyloadapi,
                entity_description=description,
                client_name=entry.title,
                entry_id=entry.entry_id,
            )
            for description in SENSOR_DESCRIPTIONS
        ),
        True,
    )


class PyLoadSensor(SensorEntity):
    """Representation of a pyLoad sensor."""

    def __init__(
        self,
        api: PyLoadAPI,
        entity_description: SensorEntityDescription,
        client_name: str,
        entry_id: str,
    ) -> None:
        """Initialize a new pyLoad sensor."""
        self._attr_name = f"{client_name} {entity_description.name}"
        self.type = entity_description.key
        self.api = api
        self._attr_unique_id = f"{entry_id}_{entity_description.key}"
        self.entity_description = entity_description
        self._attr_available = False
        self.data: StatusServerResponse

    async def async_update(self) -> None:
        """Update state of sensor."""
        start = monotonic()
        try:
            status = await self.api.get_status()
        except InvalidAuth:
            _LOGGER.info("Authentication failed, trying to reauthenticate")
            try:
                await self.api.login()
            except InvalidAuth:
                _LOGGER.error(
                    "Authentication failed for %s, check your login credentials",
                    self.api.username,
                )
                return
            else:
                _LOGGER.info(
                    "Unable to retrieve data due to cookie expiration "
                    "but re-authentication was successful"
                )
                return
            finally:
                self._attr_available = False

        except CannotConnect:
            _LOGGER.debug("Unable to connect and retrieve data from pyLoad API")
            self._attr_available = False
            return
        except ParserError:
            _LOGGER.error("Unable to parse data from pyLoad API")
            self._attr_available = False
            return
        else:
            self.data = status
            _LOGGER.debug(
                "Finished fetching pyload data in %.3f seconds",
                monotonic() - start,
            )

        self._attr_available = True

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.data.get(self.entity_description.key)
