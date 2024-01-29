"""This component provides support for virtual components."""

from distutils import util
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_SOURCE, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service import verify_domain_control
from homeassistant.helpers.typing import ConfigType

from .cfg import BlendedCfg
from .const import *

__version__ = "0.9.0a6"

_LOGGER = logging.getLogger(__name__)

# Purely to quieten down the checks.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})

SERVICE_AVAILABILE = "set_available"
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Required("value"): cv.boolean,
    }
)

VIRTUAL_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.DEVICE_TRACKER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up a virtual component."""

    hass.data[COMPONENT_DOMAIN] = {}
    hass.data[COMPONENT_SERVICES] = {}

    # See if we have already imported the data. If we haven't then do it now.
    config_entry = _async_find_matching_config_entry(hass)
    if not config_entry:
        _LOGGER.debug("importing a YAML setup")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                COMPONENT_DOMAIN, context={CONF_SOURCE: SOURCE_IMPORT}, data=config
            )
        )

        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{COMPONENT_DOMAIN}",
            is_fixable=False,
            issue_domain=COMPONENT_DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": COMPONENT_DOMAIN,
                "integration_title": "Virtual",
            },
        )

        return True

    _LOGGER.debug("ignoring a YAML setup")
    return True


@callback
def _async_find_matching_config_entry(hass):
    """If we have anything in config_entries for virtual we consider it
    configured and will ignore the YAML.
    """
    for entry in hass.config_entries.async_entries(COMPONENT_DOMAIN):
        return entry


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug(f"async setup {entry.data}")

    # Set up hass data if necessary
    if COMPONENT_DOMAIN not in hass.data:
        hass.data[COMPONENT_DOMAIN] = {}
        hass.data[COMPONENT_SERVICES] = {}

    # Get the config.
    _LOGGER.debug("creating new cfg")
    vcfg = BlendedCfg(entry.data)
    vcfg.load()

    # create the devices.
    _LOGGER.debug("creating the devices")
    for device in vcfg.devices:
        _LOGGER.debug(f"creating-device={device}")
        await _async_get_or_create_virtual_device_in_registry(hass, entry, device)

    # Update the component data.
    hass.data[COMPONENT_DOMAIN].update(
        {
            entry.data[ATTR_GROUP_NAME]: {
                ATTR_ENTITIES: vcfg.entities,
                ATTR_FILE_NAME: entry.data[ATTR_FILE_NAME],
            }
        }
    )
    _LOGGER.debug(f"update hass data {hass.data[COMPONENT_DOMAIN]}")

    # Create the entities.
    _LOGGER.debug("creating the entities")
    await hass.config_entries.async_forward_entry_setups(entry, VIRTUAL_PLATFORMS)

    # Install service handler.
    @verify_domain_control(hass, COMPONENT_DOMAIN)
    async def async_virtual_service_set_available(call) -> None:
        """Call virtual service handler."""
        _LOGGER.info(f"{call.service} service called")
        await async_virtual_set_availability_service(hass, call)

    if not hasattr(hass.data[COMPONENT_SERVICES], COMPONENT_DOMAIN):
        _LOGGER.debug("installing handlers")
        hass.data[COMPONENT_SERVICES][COMPONENT_DOMAIN] = "installed"
        hass.services.async_register(
            COMPONENT_DOMAIN, SERVICE_AVAILABILE, async_virtual_service_set_available
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(f"unloading virtual group {entry.data[ATTR_GROUP_NAME]}")
    # _LOGGER.debug(f"before hass={hass.data[COMPONENT_DOMAIN]}")
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, VIRTUAL_PLATFORMS
    )
    if unload_ok:
        bcfg = BlendedCfg(entry.data)
        bcfg.delete()
        hass.data[COMPONENT_DOMAIN].pop(entry.data[ATTR_GROUP_NAME])
    # _LOGGER.debug(f"after hass={hass.data[COMPONENT_DOMAIN]}")

    return unload_ok


async def _async_get_or_create_virtual_device_in_registry(
    hass: HomeAssistant, entry: ConfigEntry, device
) -> None:
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(COMPONENT_DOMAIN, device[ATTR_DEVICE_ID])},
        manufacturer=COMPONENT_MANUFACTURER,
        model=COMPONENT_MODEL,
        name=device[CONF_NAME],
        sw_version=__version__,
    )


def get_entity_configs(hass, group_name, domain):
    return (
        hass.data.get(COMPONENT_DOMAIN, {})
        .get(group_name, {})
        .get(ATTR_ENTITIES, {})
        .get(domain, [])
    )


def get_entity_from_domain(hass, domain, entity_id):
    component = hass.data.get(domain)
    if component is None:
        raise HomeAssistantError(f"{domain} component not set up")

    entity = component.get_entity(entity_id)
    if entity is None:
        raise HomeAssistantError(f"{entity_id} not found")

    return entity


async def async_virtual_set_availability_service(hass, call):
    entities = call.data["entity_id"]
    value = call.data["value"]

    if type(value) is not bool:
        value = bool(util.strtobool(value))

    for entity_id in entities:
        domain = entity_id.split(".")[0]
        _LOGGER.info(f"{entity_id} set_avilable(value={value})")
        get_entity_from_domain(hass, domain, entity_id).set_available(value)
