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
from .const import DOMAIN, DEFAULT_PORT
from .models import BaseMediaPlayerFactory

_LOGGER = logging.getLogger(__name__)


class PlexampConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plexamp Media Player."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        data_schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("plex_ip_address"): str,
                vol.Optional("plex_token"): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="add_plexamp_device",
                data_schema=data_schema,
                errors=errors,
            )

    async def async_step_add_plexamp_device(
        self, user_input=None, errors=None
    ) -> FlowResult:
        """
        Add a Plexamp device to Home Assistant.

        Args:
            user_input (dict): User input data.
            errors (dict): Form validation errors.

        Returns:
            FlowResult: The result of the flow step.
        """
        data_schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Required("plex_ip_address"): str,
                vol.Required("plex_token"): str,
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
            step_id="add_plexamp_device",
            data_schema=data_schema,
            errors=errors,
        )

    async def _async_add_plexamp_device(self, user_input):
        host = user_input.get(CONF_HOST)
        plex_token = user_input.get("plex_token")
        plex_ip_address = user_input.get("plex_ip_address")

        device = None
        try:
            if plex_token and plex_ip_address:
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

    async def _async_test_authenticated_connection(
        self, hass: HomeAssistant, host: str, plex_token: str, plex_ip_address: str
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
                    found_server = await self._get_server_info(
                        hass=hass,
                        plex_token=plex_token,
                        plex_ip_address=plex_ip_address,
                    )

                    for device in devices:
                        first_connection = device.get("connections", [{}])[0]
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

    @staticmethod
    async def _get_server_info(
        hass: HomeAssistant, plex_token: str, plex_ip_address: str
    ) -> dict:
        headers = {
            "X-Plex-Token": plex_token,
            "X-Plex-Client-Identifier": "Plex_HomeAssistant",
            "X-Plex-Product": "Plex_HomeAssistant",
            "Accept": "application/json",
        }
        server_url = "https://plex.tv/api/v2/resources?includeHttps=1&includeRelay=0"
        session = async_get_clientsession(hass)
        found_server = {}
        async with session.get(server_url, headers=headers, timeout=10) as response:
            if response.status == 200:
                devices = await response.json()

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
                    return found_server
                return found_server
        return found_server
