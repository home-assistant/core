"""Support for Agent."""
import asyncio
import logging

from agent import AgentError
from agent.a import Agent

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONNECTION, DOMAIN as AGENT_DOMAIN, SERVER_URL

ATTRIBUTION = "ispyconnect.com"
DEFAULT_BRAND = "Agent DVR by ispyconnect.com"

_LOGGER = logging.getLogger(__name__)

FORWARDS = ["alarm_control_panel", "camera"]


async def async_setup(hass, config):
    """Old way to set up integrations."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Agent component."""
    hass.data.setdefault(AGENT_DOMAIN, {})

    server_origin = config_entry.data[SERVER_URL]

    agent_client = Agent(server_origin, async_get_clientsession(hass))
    try:
        await agent_client.update()
    except AgentError as err:
        await agent_client.close()
        raise ConfigEntryNotReady from err

    if not agent_client.is_available:
        raise ConfigEntryNotReady

    await agent_client.get_devices()

    hass.data[AGENT_DOMAIN][config_entry.entry_id] = {CONNECTION: agent_client}

    device_registry = await dr.async_get_registry(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(AGENT_DOMAIN, agent_client.unique)},
        manufacturer="iSpyConnect",
        name=f"Agent {agent_client.name}",
        model="Agent DVR",
        sw_version=agent_client.version,
    )

    for forward in FORWARDS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, forward)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, forward)
                for forward in FORWARDS
            ]
        )
    )

    await hass.data[AGENT_DOMAIN][config_entry.entry_id][CONNECTION].close()

    if unload_ok:
        hass.data[AGENT_DOMAIN].pop(config_entry.entry_id)

    return unload_ok
