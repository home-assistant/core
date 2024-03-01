"""Handle a config flow for Plexamp Media Player."""

import logging
import defusedxml.ElementTree as ET

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .models import BaseMediaPlayerFactory

from .const import (
    CONF_PLEX_TOKEN,
    DOMAIN, ADD_SONOS,
)

_LOGGER = logging.getLogger(__name__)


class PlexampConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plexamp Media Player."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate user input
            host = user_input.get(CONF_HOST)
            plex_token = user_input.get(CONF_PLEX_TOKEN)
            add_sonos = user_input.get(ADD_SONOS)
            # Example validation: Check if it's an IP address or a domain name (basic validation)
            try:
                (
                    connection_successful,
                    device,
                ) = await self._async_test_connection(self.hass, host)

                if not connection_successful:
                    _LOGGER.error(
                        "Couldn't connect to Plexamp, connection was not successful"
                    )
                    errors["base"] = "invalid_host"

                if not errors:
                    # If validation passes, proceed to look for sonos devices and create entries
                    _LOGGER.debug("identifier: %s", device.identifier)
                    await self.async_set_unique_id(device.identifier)
                    self._abort_if_unique_id_configured()
                    await self._async_create_media_player_entry(device)

                    sonos_devices: list[BaseMediaPlayerFactory] = []

                    if add_sonos:
                        sonos_devices = await self._check_for_sonos_devices(self.hass, plex_token)

                    new_discovered_sonos_devices = []
                    # Create media player entries for each sonos device
                    # for device in sonos_devices:
                    #     _LOGGER.debug("identifier: %s", device.identifier)
                    #     if await self.async_set_unique_id(device.identifier):
                    #         await self._async_create_media_player_entry(device)
                    #         new_discovered_sonos_devices.append(device)
                    #     else:
                    #         errors["base"] = "non_unique_device"

                    if not errors:
                        all_devices: list[dict] = [device.to_dict() for device in [device] + sonos_devices]
                        # Return success if no errors occurred
                        entry_data = user_input.copy()  # Start with user input data
                        entry_data["devices"] = all_devices  # Add array of devices
                        return self.async_create_entry(title=device.name, data=entry_data)

            except Exception as e:
                _LOGGER.error("Error trying to connect to Plexamp: %s", e)

        # If there's user input that led to errors, or if we're showing the form initially
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): str,
                    vol.Optional("plex_token"): str,
                    vol.Optional("plex_ip_address"): str,
                    vol.Optional("add_sonos"): bool
                }
            ),
            errors=errors
        )

    async def _async_create_media_player_entry(self, device: BaseMediaPlayerFactory) -> FlowResult:
        """Create media player entry for the device."""
        entry_data = {
            "title": device.name,
            "host": device.host,
            "identifier": device.identifier,
            "ip": device.ip
        }

        # Create media player entry
        return self.async_create_entry(title=device.name, data=entry_data)

    @staticmethod
    async def _check_for_sonos_devices(hass: HomeAssistant, plex_token: str) -> list[BaseMediaPlayerFactory]:
        """Looks for sonos devices connected to Plexamp."""
        sonos_devices: list[BaseMediaPlayerFactory] = []

        headers = {
            "X-Plex-Token": plex_token,
        }
        url = "https://sonos.plex.tv/resources"
        session = async_get_clientsession(hass)

        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                response.raise_for_status()
                xml_content = await response.text()

                root = ET.fromstring(xml_content)
                players = root.findall("Player")

                for player in players:
                    identifier = player.get("machineIdentifier", "")
                    ip = player.get("lanIP", "")
                    name = player.get("title", "")
                    host = "https://sonos.plex.tv"
                    new_sonos_device = BaseMediaPlayerFactory(name=name, host=host, identifier=identifier, ip=ip)

                    sonos_devices.append(new_sonos_device)

                    _LOGGER.debug("Found player %s with id %s", name, identifier)
        except (aiohttp.ClientError, aiohttp.ClientResponseError) as e:
            _LOGGER.error("Error retrieving Sonos devices: %s", e)
        except ET.ParseError as e:
            _LOGGER.error("Error parsing XML response: %s", e)

        return sonos_devices

    @staticmethod
    async def _async_test_connection(hass: HomeAssistant, host: str) -> (bool, BaseMediaPlayerFactory):
        """Return True if connection to the provided host is successful."""

        url = f"http://{host}:32500/resources"
        session = async_get_clientsession(hass)

        _LOGGER.debug("URL: %s", url)

        try:
            async with session.get(url, timeout=10) as response:
                text = await response.text()
                root = ET.fromstring(text)

                timeline = root.find("Player")

                name = timeline.get("title", "Plexamp")
                identifier = timeline.get("machineIdentifier", url)

                device = BaseMediaPlayerFactory(name=name, host=f"http://{host}:32500", identifier=identifier, ip=host)

                _LOGGER.debug(
                    "Connection with %s was successful. New media_player found: %s",
                    url,
                    name,
                )

                return response.status == 200, device

        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout trying to connect to Plexamp")

        return False, None