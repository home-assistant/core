"""Support for the Tank Utility propane monitor."""

import datetime as dt
import logging

import probatio
import requests
from tank_utility import auth, device as tank_monitor

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD, PERCENTAGE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = dt.timedelta(hours=1)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_EMAIL): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
        probatio.Required(CONF_DEVICES): probatio.All(
            probatio.EnsureList(), probatio.NonEmpty()
        ),
    }
)

SENSOR_TYPE = "tank"
SENSOR_ROUNDING_PRECISION = 1
SENSOR_ATTRS = [
    "name",
    "address",
    "capacity",
    "fuelType",
    "orientation",
    "status",
    "time",
    "time_iso",
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tank Utility sensor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and (reason := result.get("reason")) != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            breaks_in_ha_version="2027.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.4.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Tank Utility",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tank Utility sensor from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    devices = entry.data[CONF_DEVICES]

    try:
        token = await hass.async_add_executor_job(auth.get_token, email, password)
    except requests.exceptions.HTTPError as http_error:
        if http_error.response.status_code == requests.codes.unauthorized:
            _LOGGER.error("Invalid credentials")
            return
        raise

    all_sensors = []
    for device in devices:
        sensor = TankUtilitySensor(email, password, token, device)
        all_sensors.append(sensor)
    async_add_entities(all_sensors, True)


class TankUtilitySensor(SensorEntity):
    """Representation of a Tank Utility sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, email, password, token, device):
        """Initialize the sensor."""
        self._email = email
        self._password = password
        self._token = token
        self._device = device
        self._attr_name = f"Tank Utility {device}"
        self._attr_unique_id = device

    def get_data(self):
        """Get data from the device.

        Flatten dictionary to map device to map of device data.

        """

        data = {}
        try:
            data = tank_monitor.get_device_data(self._token, self._device)
        except requests.exceptions.HTTPError as http_error:
            if http_error.response.status_code in (
                requests.codes.unauthorized,
                requests.codes.bad_request,
            ):
                _LOGGER.debug("Getting new token")
                self._token = auth.get_token(self._email, self._password, force=True)
                data = tank_monitor.get_device_data(self._token, self._device)
            else:
                raise
        data.update(data.pop("device", {}))
        data.update(data.pop("lastReading", {}))
        return data

    def update(self) -> None:
        """Set the device state and attributes."""
        data = self.get_data()
        self._attr_native_value = round(data[SENSOR_TYPE], SENSOR_ROUNDING_PRECISION)
        self._attr_extra_state_attributes = {
            k: v for k, v in data.items() if k in SENSOR_ATTRS
        }
