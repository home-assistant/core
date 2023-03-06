"""Config flow for the Open Thread Border Router integration."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import aiohttp
import python_otbr_api
from python_otbr_api import tlv_parser
import voluptuous as vol

from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.thread import (
    async_add_dataset,
    async_get_preferred_dataset,
    async_set_preferred_dataset,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_CHANNEL, DOMAIN

if TYPE_CHECKING:
    from . import OTBRData

_LOGGER = logging.getLogger(__name__)


class OTBRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Open Thread Border Router."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OTBROptionsFlow:
        """Get the options flow for this handler."""
        return OTBROptionsFlow(config_entry)

    async def _connect_and_create_dataset(self, url: str) -> None:
        """Connect to the OTBR and create a dataset if it doesn't have one."""
        api = python_otbr_api.OTBR(url, async_get_clientsession(self.hass), 10)
        if await api.get_active_dataset_tlvs() is None:
            # We currently have no way to know which channel zha is using, assume it's
            # the default
            zha_channel = DEFAULT_CHANNEL
            thread_dataset_channel = None
            thread_dataset_tlv = await async_get_preferred_dataset(self.hass)
            if thread_dataset_tlv:
                dataset = tlv_parser.parse_tlv(thread_dataset_tlv)
                if channel_str := dataset.get(tlv_parser.MeshcopTLVType.CHANNEL):
                    thread_dataset_channel = int(channel_str, base=16)

            if thread_dataset_tlv is not None and zha_channel == thread_dataset_channel:
                await api.set_active_dataset_tlvs(bytes.fromhex(thread_dataset_tlv))
            else:
                _LOGGER.debug(
                    "not importing TLV with channel %s", thread_dataset_channel
                )
                await api.create_active_dataset(
                    python_otbr_api.OperationalDataSet(
                        channel=zha_channel, network_name="home-assistant"
                    )
                )
            await api.set_enabled(True)

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Set up by user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            url = user_input[CONF_URL]
            try:
                await self._connect_and_create_dataset(url)
            except (
                python_otbr_api.OTBRError,
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(DOMAIN)
                return self.async_create_entry(
                    title="Open Thread Border Router",
                    data=user_input,
                )

        data_schema = vol.Schema({CONF_URL: str})
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Handle hassio discovery."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        config = discovery_info.config
        url = f"http://{config['host']}:{config['port']}"

        try:
            await self._connect_and_create_dataset(url)
        except python_otbr_api.OTBRError as exc:
            _LOGGER.warning("Failed to communicate with OTBR@%s: %s", url, exc)
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(DOMAIN)
        return self.async_create_entry(
            title="Open Thread Border Router",
            data={CONF_URL: url},
        )


class OTBROptionsFlow(OptionsFlowWithConfigEntry):
    """Handle OTBR options."""

    async def async_step_init(self, user_input: None = None) -> FlowResult:
        """Manage the OTBR options."""
        if DOMAIN not in self.hass.data:
            return self.async_abort(reason="config_entry_not_setup")

        data: OTBRData = self.hass.data[DOMAIN]

        menu_options = ["create_network"]
        placeholders = {}

        otbr_dataset: dict[tlv_parser.MeshcopTLVType, str] | None = None
        preferred_dataset: dict[tlv_parser.MeshcopTLVType, str] | None = None

        try:
            if otbr_dataset_tlv := await data.get_active_dataset_tlvs():
                otbr_dataset = tlv_parser.parse_tlv(otbr_dataset_tlv.hex())
        except HomeAssistantError:
            _LOGGER.warning("Could not read active dataset", exc_info=True)

        if preferred_dataset_tlv := await async_get_preferred_dataset(self.hass):
            preferred_dataset = tlv_parser.parse_tlv(preferred_dataset_tlv)

        if otbr_dataset and otbr_dataset != preferred_dataset:
            menu_options.append("prefer_otbr_network")
            placeholders["otbr_network"] = otbr_dataset.get(
                tlv_parser.MeshcopTLVType.NETWORKNAME, ""
            )

        if preferred_dataset and preferred_dataset != otbr_dataset:
            menu_options.append("use_preferred_network")
            placeholders["preferred_network"] = preferred_dataset.get(
                tlv_parser.MeshcopTLVType.NETWORKNAME, ""
            )

        self.context["placeholders"] = placeholders
        return self.async_show_menu(
            step_id="thread_network_menu",
            menu_options=menu_options,
            description_placeholders=placeholders,
        )

    async def async_step_create_network(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create a new network, and optionally mark it as preferred."""
        if user_input is not None:
            data: OTBRData = self.hass.data[DOMAIN]

            # We currently have no way to know which channel zha is using, assume it's
            # the default
            zha_channel = DEFAULT_CHANNEL

            try:
                # Disable the router, create a new network and read it back
                await data.set_enabled(False)
                await data.create_active_dataset(
                    python_otbr_api.OperationalDataSet(
                        channel=zha_channel, network_name="home-assistant"
                    )
                )
                await data.set_enabled(True)
                dataset_tlvs = await data.get_active_dataset_tlvs()
            except HomeAssistantError:
                _LOGGER.warning("Failed to create new Thread network", exc_info=True)
                return self.async_abort(reason="unknown")
            if not dataset_tlvs:
                _LOGGER.warning("Got empty network")
                return self.async_abort(reason="unknown")

            dataset_id = await async_add_dataset(
                self.hass, self._config_entry.title, dataset_tlvs.hex()
            )
            await async_set_preferred_dataset(self.hass, dataset_id)

            return self.async_create_entry(data={})

        return self.async_show_form(step_id="create_network")

    async def async_step_prefer_otbr_network(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Make the OTBR's network the preferred network."""

        if user_input is not None:
            data: OTBRData = self.hass.data[DOMAIN]

            try:
                dataset_tlvs = await data.get_active_dataset_tlvs()
            except HomeAssistantError:
                _LOGGER.warning("Failed to get the active network", exc_info=True)
                return self.async_abort(reason="unknown")
            if not dataset_tlvs:
                _LOGGER.warning("Got empty network")
                return self.async_abort(reason="unknown")

            dataset_id = await async_add_dataset(
                self.hass, self._config_entry.title, dataset_tlvs.hex()
            )
            await async_set_preferred_dataset(self.hass, dataset_id)

            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="prefer_otbr_network",
            description_placeholders=self.context["placeholders"],
        )

    async def async_step_use_preferred_network(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Make the OTBR use the preferred network."""

        if not (thread_dataset_tlv := await async_get_preferred_dataset(self.hass)):
            _LOGGER.warning("No preferred network")
            return self.async_abort(reason="unknown")

        if user_input is not None:
            data: OTBRData = self.hass.data[DOMAIN]

            try:
                await data.set_enabled(False)
                await data.set_active_dataset_tlvs(bytes.fromhex(thread_dataset_tlv))
                await data.set_enabled(True)
            except HomeAssistantError:
                return self.async_abort(reason="unknown")

            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="use_preferred_network",
            description_placeholders=self.context["placeholders"],
        )
