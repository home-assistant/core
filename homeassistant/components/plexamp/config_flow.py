"""Handle a config flow for Plexamp Media Player."""

import logging

import aiohttp
import defusedxml.ElementTree as ET
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PLEX_TOKEN, DOMAIN
from .models import BaseMediaPlayerFactory

_LOGGER = logging.getLogger(__name__)


class PlexampConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plexamp Media Player."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is None:
            # Display initial form to choose an option
            return self.async_step_show_option_form(errors=errors)
        if user_input["option"] == "new_device_without_metadata":
            return await self.async_step_add_plexamp_device(errors=errors)
        if user_input["option"] == "new_device_with_metadata":
            return await self.async_step_add_plexamp_device(
                errors=errors, with_metadata=True
            )
        if user_input["option"] == "sonos_devices":
            return await self.async_step_add_sonos_devices(errors=errors)

        return self.async_step_show_option_form(
            errors={"base": "Invalid option selected"}
        )

    def async_step_show_option_form(self, errors=None) -> FlowResult:
        options = {
            "new_device_without_metadata": "new_device_without_metadata",
            "new_device_with_metadata": "new_device_with_metadata",
            "sonos_devices": "sonos_devices",
        }

        # Create form schema for selecting an option
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("option"): vol.In(options.keys())}),
            errors=errors,
        )

    async def async_step_add_plexamp_device(
        self, user_input=None, errors=None, with_metadata=False
    ) -> FlowResult:
        with_metadata_schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Required("plex_ip_address"): str,
                vol.Required("plex_token"): str,
            }
        )

        no_metadata_schema = vol.Schema(
            {
                vol.Required("host"): str,
            }
        )

        if user_input is not None:
            host = user_input.get(CONF_HOST)
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
                    _LOGGER.debug("identifier: %s", device.identifier)
                    await self.async_set_unique_id(device.identifier)
                    self._abort_if_unique_id_configured()
                    entry_data = user_input.copy()
                    entry_data["devices"] = [device.to_dict()]
                    return self.async_create_entry(title=device.name, data=entry_data)

            except Exception as e:
                _LOGGER.error("Error trying to connect to Plexamp: %s", e)
                return self.async_show_form(
                    step_id="add_plexamp_device",
                    data_schema=with_metadata_schema
                    if with_metadata
                    else no_metadata_schema,
                    errors=errors,
                )

        return self.async_show_form(
            step_id="add_plexamp_device",
            data_schema=with_metadata_schema if with_metadata else no_metadata_schema,
            errors=errors,
        )

    async def async_step_add_sonos_devices(
        self, user_input=None, errors=None
    ) -> FlowResult:
        """Create form schema for looking for sonos devices"""
        if user_input is not None:
            # Validate user input
            plex_token = user_input.get(CONF_PLEX_TOKEN)

            sonos_devices = await self._check_for_sonos_devices(self.hass, plex_token)

            if not errors:
                all_devices: list[dict] = [device.to_dict() for device in sonos_devices]
                # Return success if no errors occurred
                entry_data = user_input.copy()  # Start with user input data
                entry_data["devices"] = all_devices  # Add array of devices
                return self.async_create_entry(title="Plexamp Sonos", data=entry_data)

        # Create form schema for selecting Sonos devices
        return self.async_show_form(
            step_id="add_sonos_devices",
            data_schema=vol.Schema(
                {
                    vol.Required("plex_ip_address"): str,
                    vol.Required("plex_token"): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    async def _check_for_sonos_devices(
        hass: HomeAssistant, plex_token: str
    ) -> list[BaseMediaPlayerFactory]:
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
                    new_sonos_device = BaseMediaPlayerFactory(
                        name=name, host=host, identifier=identifier, ip=ip
                    )

                    sonos_devices.append(new_sonos_device)

                    _LOGGER.debug("Found player %s with id %s", name, identifier)
        except (aiohttp.ClientError, aiohttp.ClientResponseError) as e:
            _LOGGER.error("Error retrieving Sonos devices: %s", e)
        except ET.ParseError as e:
            _LOGGER.error("Error parsing XML response: %s", e)

        return sonos_devices

    @staticmethod
    async def _async_test_connection(
        hass: HomeAssistant, host: str
    ) -> (bool, BaseMediaPlayerFactory):
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

                device = BaseMediaPlayerFactory(
                    name=name,
                    host=f"http://{host}:32500",
                    identifier=identifier,
                    ip=host,
                )

                _LOGGER.debug(
                    "Connection with %s was successful. New media_player found: %s",
                    url,
                    name,
                )

                return response.status == 200, device

        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout trying to connect to Plexamp")

        return False, None
