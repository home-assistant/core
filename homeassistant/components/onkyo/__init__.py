"""The onkyo component."""
import asyncio
import logging

from eiscp import eISCP as onkyo_rcv
from eiscp.commands import COMMANDS
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components.media_player.const import DOMAIN as media_domain
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.helpers import (
    config_per_platform,
    config_validation as cv,
    device_registry as dr,
)

from .const import (
    ACCEPTED_VALUES,
    ATTR_HDMI_OUTPUT,
    COMPONENTS,
    CONF_SOURCES,
    DOMAIN,
    SERVICE_SELECT_HDMI_OUTPUT,
)

ONKYO_SELECT_OUTPUT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_HDMI_OUTPUT): vol.In(ACCEPTED_VALUES),
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the onkyo environment."""
    hass.data.setdefault(DOMAIN, {})

    # Import configuration from media_player platform
    config_platform = config_per_platform(config, media_domain)
    for p_type, p_config in config_platform:
        if p_type != DOMAIN:
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=p_config,
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set the config entry up."""
    if not config_entry.options:
        sources = config_entry.data.get(CONF_SOURCES, {})
        if isinstance(sources, list):
            sources = list2dict(sources)
        hass.config_entries.async_update_entry(
            config_entry,
            options={CONF_SOURCES: sources},
        )

    try:
        receiver = onkyo_rcv(config_entry.data[CONF_HOST])
        hass.data[DOMAIN][config_entry.unique_id] = receiver
    except CannotConnect as err:
        raise exceptions.ConfigEntryNotReady from err

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.unique_id)},
        manufacturer="Onkyo",
        model=receiver.model_name,
    )

    hosts = []

    async def async_service_handler(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        devices = [d for d in hosts if d.entity_id in entity_ids]
        for device in devices:
            if service.service == SERVICE_SELECT_HDMI_OUTPUT:
                device.select_output(service.data.get(ATTR_HDMI_OUTPUT))

    hass.services.async_register(
        DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        async_service_handler,
        schema=ONKYO_SELECT_OUTPUT_SCHEMA,
    )

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    if not config_entry.update_listeners:
        config_entry.add_update_listener(async_update_options)

    return True


async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in COMPONENTS
            ]
        )
    )
    if unload_ok:
        receiver = hass.data[DOMAIN][config_entry.unique_id]
        await hass.async_add_executor_job(receiver.disconnect)
    return unload_ok


def default_sources() -> dict:
    """Retrieve default sources."""
    sources_list = {}
    for value in COMMANDS["main"]["SLI"]["values"].values():
        name = value["name"]
        desc = value["description"].replace("sets ", "")
        if isinstance(name, tuple):
            name = name[0]
        if name in ["07", "08", "09", "up", "down", "query"]:
            continue
        sources_list.update({name: desc})
    return sources_list


def list2dict(sources: list) -> dict:
    """Reduce selected sources in default sources."""
    return {key: value for key, value in default_sources().items() if key in sources}


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
