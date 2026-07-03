"""Integration with the Rachio Iro sprinkler system controller."""

import logging
import secrets

from rachiopy import Rachio
from requests.exceptions import ConnectTimeout
import voluptuous as vol

from homeassistant.components import cloud
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ID,
    CONF_API_KEY,
    CONF_WEBHOOK_ID,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CLOUDHOOK_URL,
    CONF_MANUAL_RUN_MINS,
    DOMAIN,
    KEY_ID,
    MODEL_GENERATION_1,
    SERVICE_PAUSE_WATERING,
    SERVICE_RESUME_WATERING,
    SERVICE_START_MULTIPLE_ZONES,
    SERVICE_STOP_WATERING,
)
from .device import RachioConfigEntry, RachioPerson
from .webhooks import (
    async_get_or_create_registered_webhook_id_and_url,
    async_register_webhook,
    async_unregister_webhook,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SWITCH]

ATTR_DEVICES = "devices"
ATTR_DURATION = "duration"
ATTR_SORT_ORDER = "sortOrder"

PAUSE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICES): cv.string,
        vol.Optional(ATTR_DURATION, default=60): cv.positive_int,
    }
)

RESUME_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICES): cv.string})

START_MULTIPLE_ZONES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_DURATION): cv.ensure_list_csv,
    }
)

STOP_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICES): cv.string})

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Rachio integration."""
    async_register_services(hass)

    return True


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register Rachio services."""

    def stop_water(service: ServiceCall) -> None:
        """Service to stop watering on all or specific controllers."""
        for person in _async_loaded_people(hass):
            all_controllers = [rachio_iro.name for rachio_iro in person.controllers]
            devices = service.data.get(ATTR_DEVICES, all_controllers)
            for iro in person.controllers:
                if iro.name in devices:
                    iro.stop_watering()

    def pause_water(service: ServiceCall) -> None:
        """Service to pause watering on all or specific controllers."""
        duration = service.data[ATTR_DURATION]
        for person in _async_loaded_people(hass):
            all_controllers = [rachio_iro.name for rachio_iro in person.controllers]
            devices = service.data.get(ATTR_DEVICES, all_controllers)
            for iro in person.controllers:
                if (
                    iro.name in devices
                    and iro.model.split("_")[0] != MODEL_GENERATION_1
                ):
                    iro.pause_watering(duration)

    def resume_water(service: ServiceCall) -> None:
        """Service to resume watering on all or specific controllers."""
        for person in _async_loaded_people(hass):
            all_controllers = [rachio_iro.name for rachio_iro in person.controllers]
            devices = service.data.get(ATTR_DEVICES, all_controllers)
            for iro in person.controllers:
                if (
                    iro.name in devices
                    and iro.model.split("_")[0] != MODEL_GENERATION_1
                ):
                    iro.resume_watering()

    def start_multiple(service: ServiceCall) -> None:
        """Service to start multiple zones in sequence."""
        entity_reg = er.async_get(hass)
        entity_ids = service.data[ATTR_ENTITY_ID]
        duration = iter(service.data[ATTR_DURATION])
        default_time = service.data[ATTR_DURATION][0]
        people_zones: dict[RachioPerson, list[dict[str, int | str]]] = {}

        for count, entity_id in enumerate(entity_ids):
            if not (zone_info := _async_get_zone_info(hass, entity_reg, entity_id)):
                continue
            person, zone_id = zone_info
            time = int(next(duration, default_time)) * 60
            people_zones.setdefault(person, []).append(
                {
                    ATTR_ID: zone_id,
                    ATTR_DURATION: time,
                    ATTR_SORT_ORDER: count,
                }
            )

        if people_zones:
            for person, zones_list in people_zones.items():
                person.start_multiple_zones(zones_list)
            _LOGGER.debug("Starting zone(s) %s", entity_ids)
            return

        raise HomeAssistantError("No matching zones found in given entity_ids")

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_WATERING,
        stop_water,
        schema=STOP_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PAUSE_WATERING,
        pause_water,
        schema=PAUSE_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESUME_WATERING,
        resume_water,
        schema=RESUME_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MULTIPLE_ZONES,
        start_multiple,
        schema=START_MULTIPLE_ZONES_SCHEMA,
    )


@callback
def _async_loaded_people(hass: HomeAssistant) -> list[RachioPerson]:
    """Return loaded Rachio accounts."""
    return [
        entry.runtime_data for entry in hass.config_entries.async_loaded_entries(DOMAIN)
    ]


@callback
def _async_get_zone_info(
    hass: HomeAssistant, entity_reg: er.EntityRegistry, entity_id: str
) -> tuple[RachioPerson, str] | None:
    """Return the Rachio person and zone ID matching an entity ID."""
    for person in _async_loaded_people(hass):
        for controller in person.controllers:
            for zone in controller.list_zones():
                zone_entity_id = entity_reg.async_get_entity_id(
                    Platform.SWITCH,
                    DOMAIN,
                    f"{controller.controller_id}-zone-{zone[KEY_ID]}",
                )
                if zone_entity_id == entity_id:
                    return person, zone[KEY_ID]
    return None


async def async_unload_entry(hass: HomeAssistant, entry: RachioConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        async_unregister_webhook(hass, entry)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: RachioConfigEntry) -> None:
    """Remove a rachio config entry."""
    if CONF_CLOUDHOOK_URL in entry.data:
        await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])


async def async_setup_entry(hass: HomeAssistant, entry: RachioConfigEntry) -> bool:
    """Set up the Rachio config entry."""

    config = entry.data
    options = entry.options

    # CONF_MANUAL_RUN_MINS can only come from a yaml import
    if not options.get(CONF_MANUAL_RUN_MINS) and config.get(CONF_MANUAL_RUN_MINS):
        options_copy = options.copy()
        options_copy[CONF_MANUAL_RUN_MINS] = config[CONF_MANUAL_RUN_MINS]
        hass.config_entries.async_update_entry(entry, options=options_copy)

    # Configure API
    api_key = config[CONF_API_KEY]
    rachio = Rachio(api_key)

    # Get the URL of this server
    rachio.webhook_auth = secrets.token_hex()
    try:
        webhook_url = await async_get_or_create_registered_webhook_id_and_url(
            hass, entry
        )
    except cloud.CloudNotConnected as exc:
        # User has an active cloud subscription, but the connection to the cloud is down
        raise ConfigEntryNotReady from exc
    rachio.webhook_url = webhook_url

    person = RachioPerson(rachio, entry)

    # Get the API user
    try:
        await person.async_setup(hass)
    except ConfigEntryAuthFailed as error:
        # Reauth is not yet implemented
        _LOGGER.error("Authentication failed: %s", error)
        return False
    except ConnectTimeout as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        raise ConfigEntryNotReady from error

    # Check for Rachio controller devices
    if not person.controllers and not person.base_stations:
        _LOGGER.error("No Rachio devices found in account %s", person.username)
        return False
    _LOGGER.debug(
        (
            "%d Rachio device(s) found; The url %s must be accessible from the internet"
            " in order to receive updates"
        ),
        len(person.controllers) + len(person.base_stations),
        webhook_url,
    )

    for base in person.base_stations:
        await base.status_coordinator.async_config_entry_first_refresh()
        await base.schedule_coordinator.async_config_entry_first_refresh()

    # Enable platform
    entry.runtime_data = person
    async_register_webhook(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
