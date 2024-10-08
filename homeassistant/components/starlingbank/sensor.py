"""Support for balance data via the Starling Bank API."""

from __future__ import annotations

from datetime import timedelta
import logging

import requests
from starlingbank import StarlingAccount
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

BALANCE_TYPES = ["cleared_balance", "effective_balance"]

CONF_ACCOUNTS = "accounts"
CONF_BALANCE_TYPES = "balance_types"
CONF_SANDBOX = "sandbox"

DEFAULT_SANDBOX = False
DEFAULT_ACCOUNT_NAME = "Starling"


SCAN_INTERVAL = timedelta(seconds=180)

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Optional(CONF_BALANCE_TYPES, default=BALANCE_TYPES): vol.All(
            cv.ensure_list, [vol.In(BALANCE_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_ACCOUNT_NAME): cv.string,
        vol.Optional(CONF_SANDBOX, default=DEFAULT_SANDBOX): cv.boolean,
    }
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_ACCOUNTS): vol.Schema([ACCOUNT_SCHEMA])}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Sterling Bank sensor platform."""

    sensors: list[StarlingBalanceSensor] = []
    for account in config[CONF_ACCOUNTS]:
        try:
            starling_account = StarlingAccount(
                account[CONF_ACCESS_TOKEN], sandbox=account[CONF_SANDBOX]
            )
            sensors.extend(
                StarlingBalanceSensor(
                    starling_account, account[CONF_NAME], balance_type
                )
                for balance_type in account[CONF_BALANCE_TYPES]
            )
        except requests.exceptions.HTTPError as error:
            _LOGGER.error(
                "Unable to set up Starling account '%s': %s", account[CONF_NAME], error
            )

    add_devices(sensors, True)


class StarlingBalanceSensor(SensorEntity):
    """Representation of a Starling balance sensor."""

    _attr_icon = "mdi:currency-gbp"

    def __init__(self, starling_account, account_name, balance_data_type):
        """Initialize the sensor."""
        self._starling_account = starling_account
        self._balance_data_type = balance_data_type
        self._state = None
        self._account_name = account_name

    @property
    def name(self):
        """Return the name of the sensor."""
        balance_data_type = self._balance_data_type.replace("_", " ").capitalize()
        return f"{self._account_name} {balance_data_type}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._starling_account.currency

    def update(self) -> None:
        """Fetch new state data for the sensor."""
        self._starling_account.update_balance_data()
        if self._balance_data_type == "cleared_balance":
            self._state = self._starling_account.cleared_balance / 100
        elif self._balance_data_type == "effective_balance":
            self._state = self._starling_account.effective_balance / 100
