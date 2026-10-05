"""The tractive integration."""

import aiotractive

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_ID, DOMAIN
from .coordinator import TractiveConfigEntry, TractiveCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: TractiveConfigEntry) -> bool:
    """Set up tractive from a config entry."""
    client = aiotractive.Tractive(
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        client_id=CLIENT_ID,
    )
    coordinator = TractiveCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register the tracker devices so entities on the pet devices can resolve
    # their via_device link at construction time.
    device_registry = dr.async_get(hass)
    for trackable in coordinator.trackables:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            configuration_url="https://my.tractive.com/",
            identifiers={(DOMAIN, trackable.tracker_id)},
            translation_key="tracker",
            translation_placeholders={"id": trackable.tracker_id},
            manufacturer="Tractive GmbH",
            sw_version=trackable.tracker_details["fw_version"],
            model_id=trackable.tracker_details["model_number"],
        )

    entry.async_create_background_task(hass, client.listen(), "tractive_listen")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove sensor entities that are no longer supported by the Tractive API
    entity_reg = er.async_get(hass)
    for trackable in coordinator.trackables:
        for key in ("activity_label", "calories", "sleep_label"):
            if entity_id := entity_reg.async_get_entity_id(
                SENSOR_DOMAIN, DOMAIN, f"{trackable.pet_id}_{key}"
            ):
                entity_reg.async_remove(entity_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TractiveConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
