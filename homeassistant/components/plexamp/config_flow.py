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

from .const import CONF_PLEX_TOKEN, DOMAIN, DEFAULT_PORT
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
            return await self.async_step_add_plexamp_device_with_metadata(errors=errors)
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

    async def async_step_add_plexamp_device_with_metadata(
        self, user_input=None, errors=None
    ) -> FlowResult:
        with_metadata_schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Required("plex_ip_address"): str,
                vol.Required("plex_token"): str,
            }
        )

        errors = {} if not errors else errors
        if user_input is not None:
            device = await self._async_add_plexamp_device(
                user_input=user_input, with_metadata=True
            )

            if not device:
                _LOGGER.error("Couldn't find any Plexamp device")
                errors["base"] = "invalid_host"

            if not errors:
                _LOGGER.debug("identifier: %s", device.client_identifier)
                await self.async_set_unique_id(device.client_identifier)
                self._abort_if_unique_id_configured()
                entry_data = user_input.copy()
                entry_data["devices"] = [device.to_dict()]
                return self.async_create_entry(title=device.name, data=entry_data)

        return self.async_show_form(
            step_id="add_plexamp_device_with_metadata",
            data_schema=with_metadata_schema,
            errors=errors,
        )

    async def async_step_add_plexamp_device(
        self, user_input=None, errors=None
    ) -> FlowResult:
        no_metadata_schema = vol.Schema(
            {
                vol.Required("host"): str,
            }
        )
        errors = {} if not errors else errors
        if user_input is not None:
            device = await self._async_add_plexamp_device(user_input=user_input)

            if not device:
                _LOGGER.error(
                    "Couldn't connect to Plexamp, connection was not successful"
                )
                errors["base"] = "invalid_host"

            if not errors:
                _LOGGER.debug("identifier: %s", device.client_identifier)
                await self.async_set_unique_id(device.client_identifier)
                self._abort_if_unique_id_configured()
                entry_data = user_input.copy()
                entry_data["devices"] = [device.to_dict()]
                return self.async_create_entry(title=device.name, data=entry_data)

        return self.async_show_form(
            step_id="add_plexamp_device_with_metadata",
            data_schema=no_metadata_schema,
            errors=errors,
        )

    async def _async_add_plexamp_device(self, user_input, with_metadata=False):
        host = user_input.get(CONF_HOST)
        plex_token = user_input.get("plex_token")
        plex_ip_address = user_input.get("plex_ip_address")

        device = None
        try:
            if with_metadata:
                device = await self._async_test_authenticated_connection(
                    self.hass,
                    host=host,
                    plex_token=plex_token,
                    plex_ip_address=plex_ip_address,
                )
            else:
                device = await self._async_test_connection(self.hass, host)

            return device

        except Exception as e:
            _LOGGER.error("Error trying to connect to Plexamp: %s", e)
            return device

    async def async_step_add_sonos_devices(
        self, user_input=None, errors=None
    ) -> FlowResult:
        """Create form schema for looking for sonos devices"""
        errors = {} if not errors else errors
        if user_input is not None:
            # Validate user input
            plex_token = user_input.get(CONF_PLEX_TOKEN)

            sonos_devices = await self._check_for_sonos_devices(self.hass, plex_token)
            if not len(sonos_devices):
                _LOGGER.error("Couldn't find any Sonos devices.")
                errors["base"] = "invalid_host"

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
                    name = player.get("title", "")
                    product = player.get("product")
                    platform_version = player.get("platformVersion")
                    machine_identifier = player.get("machineIdentifier", "")
                    protocol = player.get("protocol")
                    lan_ip = player.get("lanIP", "")
                    uri = "https://sonos.plex.tv"
                    server_uri = uri

                    new_sonos_device = BaseMediaPlayerFactory(
                        name=name,
                        product=product,
                        product_version=platform_version,
                        client_identifier=machine_identifier,
                        protocol=protocol,
                        address=lan_ip,
                        port="",
                        uri=uri,
                        server={},
                    )

                    sonos_devices.append(new_sonos_device)

                    _LOGGER.debug(
                        "Found player %s with id %s", name, machine_identifier
                    )
        except (aiohttp.ClientError, aiohttp.ClientResponseError) as e:
            _LOGGER.error("Error retrieving Sonos devices: %s", e)
        except ET.ParseError as e:
            _LOGGER.error("Error parsing XML response: %s", e)

        return sonos_devices

    @staticmethod
    async def _async_test_authenticated_connection(
        hass: HomeAssistant, host: str, plex_token: str, plex_ip_address: str
    ) -> BaseMediaPlayerFactory | None:
        """If the user provides authentication, we can get more info of the device and store it"""
        url = "https://plex.tv/api/v2/resources?includeHttps=1&includeRelay=0"
        session = async_get_clientsession(hass)
        _LOGGER.debug("URL: %s", url)
        headers = {
            "X-Plex-Token": plex_token,
            "X-Plex-Client-Identifier": "Plex_HomeAssistant",
            "X-Plex-Product": "Plex_HomeAssistant",
            "Accept": "application/json",
        }
        try:
            async with session.get(url, timeout=10, headers=headers) as response:
                if response.status == 200:
                    devices = await response.json()
                    found_device = None
                    found_server = {}

                    for device in devices:
                        first_connection = device.get("connections", [{}])[0]
                        if (
                            device.get("provides") == "server"
                            and first_connection.get("address") == plex_ip_address
                        ):
                            found_server["identifier"] = device.get("clientIdentifier")
                            found_server["protocol"] = first_connection.get("protocol")
                            found_server["port"] = first_connection.get("port")
                            found_server["uri"] = first_connection.get("uri")
                        if (
                            "player" in device.get("provides")
                            and first_connection.get("address") == host
                        ):
                            found_device = device

                    if found_device is None or found_server.get("identifier") is None:
                        return None

                    device = BaseMediaPlayerFactory(
                        name=found_device.get("name"),
                        product=found_device.get("product"),
                        product_version=found_device.get("productVersion"),
                        client_identifier=found_device.get("clientIdentifier", ""),
                        protocol=found_device.get("connections", [{}])[0].get(
                            "protocol"
                        ),
                        address=found_device.get("connections", [{}])[0].get("address"),
                        port=found_device.get("connections", [{}])[0].get("port"),
                        uri=found_device.get("connections", [{}])[0].get("uri"),
                        server=found_server,
                    )

                    return device
            return None
        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Connection to Plexamp could not be established")
        return None

    @staticmethod
    async def _async_test_connection(
        hass: HomeAssistant, host: str
    ) -> BaseMediaPlayerFactory | None:
        """Return True if connection to the provided host is successful."""

        url = f"http://{host}:{DEFAULT_PORT}/resources"
        session = async_get_clientsession(hass)

        _LOGGER.debug("URL: %s", url)

        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    text = await response.text()
                    root = ET.fromstring(text)

                    timeline = root.find("Player")

                    name = timeline.get("title", "Plexamp")
                    product = timeline.get("product", "Plexamp")
                    platform_version = timeline.get("platformVersion", url)
                    machine_identifier = timeline.get("machineIdentifier", url)

                    device = BaseMediaPlayerFactory(
                        name=name,
                        product=product,
                        product_version=platform_version,
                        client_identifier=machine_identifier,
                        protocol="http",
                        address=host,
                        port=DEFAULT_PORT,
                        uri=f"http://{host}:{DEFAULT_PORT}",
                        server={},
                    )

                    _LOGGER.debug(
                        "Connection with %s was successful. New media_player found: %s",
                        url,
                        name,
                    )

                    return device

            return None
        except (TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Timeout trying to connect to Plexamp")
        return None
