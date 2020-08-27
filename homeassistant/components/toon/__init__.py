"""Support for Toon van Eneco devices."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_AGREEMENT_ID, CONF_MIGRATE, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import ToonDataUpdateCoordinator
from .oauth2 import register_oauth2_implementations

ENTITY_COMPONENTS = {
    BINARY_SENSOR_DOMAIN,
    CLIMATE_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
}

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_SCAN_INTERVAL),
            vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): cv.string,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): cv.positive_time_period,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Toon components."""
    if DOMAIN not in config:
        return True

    register_oauth2_implementations(
        hass, config[DOMAIN][CONF_CLIENT_ID], config[DOMAIN][CONF_CLIENT_SECRET]
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT})
    )

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle migration of a previous version config entry."""
    if entry.version == 1:
        # There is no usable data in version 1 anymore.
        # The integration switched to OAuth and because of this, uses
        # different unique identifiers as well.
        # Force this by removing the existing entry and trigger a new flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_MIGRATE: entry.entry_id},
            )
        )
        return False

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toon from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    coordinator = ToonDataUpdateCoordinator(hass, entry=entry, session=session)
    await coordinator.toon.activate_agreement(
        agreement_id=entry.data[CONF_AGREEMENT_ID]
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register device for the Meter Adapter, since it will have no entities.
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, coordinator.data.agreement.agreement_id, "meter_adapter")
        },
        manufacturer="Eneco",
        name="Meter Adapter",
        via_device=(DOMAIN, coordinator.data.agreement.agreement_id),
    )

    # Spin up the platforms
    for component in ENTITY_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    # If Home Assistant is already in a running state, register the webhook
    # immediately, else trigger it after Home Assistant has finished starting.
    if hass.state == CoreState.running:
        await coordinator.register_webhook()
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, coordinator.register_webhook
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Toon config entry."""

    # Remove webhooks registration
    await hass.data[DOMAIN][entry.entry_id].unregister_webhook()

    # Unload entities for this entry/device.
    unload_ok = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in ENTITY_COMPONENTS
            )
        )
    )

    # Cleanup
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
