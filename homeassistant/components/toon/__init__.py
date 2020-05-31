"""Support for Toon van Eneco devices."""
from functools import partial
import logging
from typing import Any, Dict

from toonapilib import Toon
import voluptuous as vol

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import config_flow  # noqa: F401
from .const import (
    CONF_DISPLAY,
    CONF_TENANT,
    DATA_TOON,
    DATA_TOON_CLIENT,
    DATA_TOON_CONFIG,
    DATA_TOON_UPDATED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.time_period, cv.positive_timedelta),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA = vol.Schema({vol.Optional(CONF_DISPLAY): cv.string})


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Toon components."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Store config to be used during entry setup
    hass.data[DATA_TOON_CONFIG] = conf

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Set up Toon from a config entry."""

    conf = hass.data.get(DATA_TOON_CONFIG)

    toon = await hass.async_add_executor_job(
        partial(
            Toon,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            conf[CONF_CLIENT_ID],
            conf[CONF_CLIENT_SECRET],
            tenant_id=entry.data[CONF_TENANT],
            display_common_name=entry.data[CONF_DISPLAY],
        )
    )
    hass.data.setdefault(DATA_TOON_CLIENT, {})[entry.entry_id] = toon

    toon_data = await hass.async_add_executor_job(ToonData, hass, entry, toon)
    hass.data.setdefault(DATA_TOON, {})[entry.entry_id] = toon_data
    async_track_time_interval(hass, toon_data.update, conf[CONF_SCAN_INTERVAL])

    # Register device for the Meter Adapter, since it will have no entities.
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, toon.agreement.id, "meter_adapter")},
        manufacturer="Eneco",
        name="Meter Adapter",
        via_device=(DOMAIN, toon.agreement.id),
    )

    def update(call):
        """Service call to manually update the data."""
        called_display = call.data.get(CONF_DISPLAY)
        for toon_data in hass.data[DATA_TOON].values():
            if (
                called_display and called_display == toon_data.display_name
            ) or not called_display:
                toon_data.update()

    hass.services.async_register(DOMAIN, "update", update, schema=SERVICE_SCHEMA)

    for component in "binary_sensor", "climate", "sensor":
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


class ToonData:
    """Communication class for interacting with toonapilib."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigType, toon):
        """Initialize the Toon data object."""
        self._hass = hass
        self._toon = toon
        self._entry = entry
        self.agreement = toon.agreement
        self.gas = toon.gas
        self.power = toon.power
        self.solar = toon.solar
        self.temperature = toon.temperature
        self.thermostat = toon.thermostat
        self.thermostat_info = toon.thermostat_info
        self.thermostat_state = toon.thermostat_state

    @property
    def display_name(self):
        """Return the display connected to."""
        return self._entry.data[CONF_DISPLAY]

    def update(self, now=None):
        """Update all Toon data and notify entities."""
        # Ignore the TTL mechanism from client library
        # It causes a lots of issues, hence we take control over caching
        self._toon._clear_cache()  # pylint: disable=protected-access

        # Gather data from client library (single API call)
        self.gas = self._toon.gas
        self.power = self._toon.power
        self.solar = self._toon.solar
        self.temperature = self._toon.temperature
        self.thermostat = self._toon.thermostat
        self.thermostat_info = self._toon.thermostat_info
        self.thermostat_state = self._toon.thermostat_state

        # Notify all entities
        dispatcher_send(self._hass, DATA_TOON_UPDATED, self._entry.data[CONF_DISPLAY])


class ToonEntity(Entity):
    """Defines a base Toon entity."""

    def __init__(self, toon: ToonData, name: str, icon: str) -> None:
        """Initialize the Toon entity."""
        self._name = name
        self._state = None
        self._icon = icon
        self.toon = toon
        self._unsub_dispatcher = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, DATA_TOON_UPDATED, self._schedule_immediate_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from update signal."""
        self._unsub_dispatcher()

    @callback
    def _schedule_immediate_update(self, display_name: str) -> None:
        """Schedule an immediate update of the entity."""
        if display_name == self.toon.display_name:
            self.async_schedule_update_ha_state(True)


class ToonDisplayDeviceEntity(ToonEntity):
    """Defines a Toon display device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this thermostat."""
        agreement = self.toon.agreement
        model = agreement.display_hardware_version.rpartition("/")[0]
        sw_version = agreement.display_software_version.rpartition("/")[-1]
        return {
            "identifiers": {(DOMAIN, agreement.id)},
            "name": "Toon Display",
            "manufacturer": "Eneco",
            "model": model,
            "sw_version": sw_version,
        }


class ToonElectricityMeterDeviceEntity(ToonEntity):
    """Defines a Electricity Meter device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            "name": "Electricity Meter",
            "identifiers": {(DOMAIN, self.toon.agreement.id, "electricity")},
            "via_device": (DOMAIN, self.toon.agreement.id, "meter_adapter"),
        }


class ToonGasMeterDeviceEntity(ToonEntity):
    """Defines a Gas Meter device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        via_device = "meter_adapter"
        if self.toon.gas.is_smart:
            via_device = "electricity"

        return {
            "name": "Gas Meter",
            "identifiers": {(DOMAIN, self.toon.agreement.id, "gas")},
            "via_device": (DOMAIN, self.toon.agreement.id, via_device),
        }


class ToonSolarDeviceEntity(ToonEntity):
    """Defines a Solar Device device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            "name": "Solar Panels",
            "identifiers": {(DOMAIN, self.toon.agreement.id, "solar")},
            "via_device": (DOMAIN, self.toon.agreement.id, "meter_adapter"),
        }


class ToonBoilerModuleDeviceEntity(ToonEntity):
    """Defines a Boiler Module device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            "name": "Boiler Module",
            "manufacturer": "Eneco",
            "identifiers": {(DOMAIN, self.toon.agreement.id, "boiler_module")},
            "via_device": (DOMAIN, self.toon.agreement.id),
        }


class ToonBoilerDeviceEntity(ToonEntity):
    """Defines a Boiler device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            "name": "Boiler",
            "identifiers": {(DOMAIN, self.toon.agreement.id, "boiler")},
            "via_device": (DOMAIN, self.toon.agreement.id, "boiler_module"),
        }
