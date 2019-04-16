"""Support for Toon van Eneco devices."""
import logging
from typing import Any, Dict
from functools import partial

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import (config_validation as cv,
                                   device_registry as dr)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import config_flow  # noqa  pylint_disable=unused-import
from .const import (
    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_DISPLAY, CONF_TENANT,
    DATA_TOON_CLIENT, DATA_TOON_CONFIG, DOMAIN)

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Toon components."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Store config to be used during entry setup
    hass.data[DATA_TOON_CONFIG] = conf

    return True


async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigType) -> bool:
    """Set up Toon from a config entry."""
    from toonapilib import Toon

    conf = hass.data.get(DATA_TOON_CONFIG)

    toon = await hass.async_add_executor_job(partial(
        Toon, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD],
        conf[CONF_CLIENT_ID], conf[CONF_CLIENT_SECRET],
        tenant_id=entry.data[CONF_TENANT],
        display_common_name=entry.data[CONF_DISPLAY]))

    hass.data.setdefault(DATA_TOON_CLIENT, {})[entry.entry_id] = toon

    # Register device for the Meter Adapter, since it will have no entities.
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, toon.agreement.id, 'meter_adapter'),
        },
        manufacturer='Eneco',
        name="Meter Adapter",
        via_hub=(DOMAIN, toon.agreement.id)
    )

    for component in 'binary_sensor', 'climate', 'sensor':
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component))

    return True


class ToonEntity(Entity):
    """Defines a base Toon entity."""

    def __init__(self, toon, name: str, icon: str) -> None:
        """Initialize the Toon entity."""
        self._name = name
        self._state = None
        self._icon = icon
        self.toon = toon

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon


class ToonDisplayDeviceEntity(ToonEntity):
    """Defines a Toon display device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this thermostat."""
        agreement = self.toon.agreement
        model = agreement.display_hardware_version.rpartition('/')[0]
        sw_version = agreement.display_software_version.rpartition('/')[-1]
        return {
            'identifiers': {
                (DOMAIN, agreement.id),
            },
            'name': 'Toon Display',
            'manufacturer': 'Eneco',
            'model': model,
            'sw_version': sw_version,
        }


class ToonElectricityMeterDeviceEntity(ToonEntity):
    """Defines a Electricity Meter device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            'name': 'Electricity Meter',
            'identifiers': {
                (DOMAIN, self.toon.agreement.id, 'electricity'),
            },
            'via_hub': (DOMAIN, self.toon.agreement.id, 'meter_adapter'),
        }


class ToonGasMeterDeviceEntity(ToonEntity):
    """Defines a Gas Meter device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        via_hub = 'meter_adapter'
        if self.toon.gas.is_smart:
            via_hub = 'electricity'

        return {
            'name': 'Gas Meter',
            'identifiers': {
                (DOMAIN, self.toon.agreement.id, 'gas'),
            },
            'via_hub': (DOMAIN, self.toon.agreement.id, via_hub),
        }


class ToonSolarDeviceEntity(ToonEntity):
    """Defines a Solar Device device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            'name': 'Solar Panels',
            'identifiers': {
                (DOMAIN, self.toon.agreement.id, 'solar'),
            },
            'via_hub': (DOMAIN, self.toon.agreement.id, 'meter_adapter'),
        }


class ToonBoilerModuleDeviceEntity(ToonEntity):
    """Defines a Boiler Module device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            'name': 'Boiler Module',
            'manufacturer': 'Eneco',
            'identifiers': {
                (DOMAIN, self.toon.agreement.id, 'boiler_module'),
            },
            'via_hub': (DOMAIN, self.toon.agreement.id),
        }


class ToonBoilerDeviceEntity(ToonEntity):
    """Defines a Boiler device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this entity."""
        return {
            'name': 'Boiler',
            'identifiers': {
                (DOMAIN, self.toon.agreement.id, 'boiler'),
            },
            'via_hub': (DOMAIN, self.toon.agreement.id, 'boiler_module'),
        }
