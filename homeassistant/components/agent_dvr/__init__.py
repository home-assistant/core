"""Support for Agent."""

from agent import AgentError
from agent.a import Agent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SERVER_URL

ATTRIBUTION = "ispyconnect.com"
DEFAULT_BRAND = "Agent DVR by ispyconnect.com"

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.CAMERA]

AgentDVRConfigEntry = ConfigEntry[Agent]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: AgentDVRConfigEntry
) -> bool:
    """Set up the Agent component."""
    server_origin = config_entry.data[SERVER_URL]

    agent_client = Agent(server_origin, async_get_clientsession(hass))
    try:
        await agent_client.update()
    except AgentError as err:
        await agent_client.close()
        raise ConfigEntryNotReady from err

    if not agent_client.is_available:
        raise ConfigEntryNotReady

    config_entry.async_on_unload(agent_client.close)

    await agent_client.get_devices()

    config_entry.runtime_data = agent_client

    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, agent_client.unique)},
        manufacturer="iSpyConnect",
        name=f"Agent {agent_client.name}",
        model="Agent DVR",
        sw_version=agent_client.version,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: AgentDVRConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
