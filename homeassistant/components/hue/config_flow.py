"""Config flow to configure Philips Hue."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohue import LinkButtonNotPressed, create_app_key
from aiohue.discovery import DiscoveredHueBridge, discover_bridge, discover_nupnp
from aiohue.util import normalize_bridge_id
import slugify as unicode_slug
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_API_VERSION, CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_UNREACHABLE,
    CONF_IGNORE_AVAILABILITY,
    DEFAULT_ALLOW_HUE_GROUPS,
    DEFAULT_ALLOW_UNREACHABLE,
    DOMAIN,
)
from .errors import CannotConnect

LOGGER = logging.getLogger(__name__)

HUE_MANUFACTURERURL = ("http://www.philips.com", "http://www.philips-hue.com")
HUE_IGNORED_BRIDGE_NAMES = ["Home Assistant Bridge", "Espalexa"]
HUE_MANUAL_BRIDGE_ID = "manual"


class HueFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Hue config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HueV1OptionsFlowHandler | HueV2OptionsFlowHandler:
        """Get the options flow for this handler."""
        if config_entry.data.get(CONF_API_VERSION, 1) == 1:
            return HueV1OptionsFlowHandler()
        return HueV2OptionsFlowHandler()

    def __init__(self) -> None:
        """Initialize the Hue flow."""
        self.bridge: DiscoveredHueBridge | None = None
        self.discovered_bridges: dict[str, DiscoveredHueBridge] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    async def _get_bridge(
        self, host: str, bridge_id: str | None = None
    ) -> DiscoveredHueBridge:
        """Return a DiscoveredHueBridge object."""
        try:
            bridge = await discover_bridge(
                host, websession=aiohttp_client.async_get_clientsession(self.hass)
            )
        except aiohttp.ClientError as err:
            LOGGER.warning(
                "Error while attempting to retrieve discovery information, "
                "is there a bridge alive on IP %s ?",
                host,
                exc_info=err,
            )
            return None
        if bridge_id is not None:
            bridge_id = normalize_bridge_id(bridge_id)
            assert bridge_id == bridge.id
        return bridge

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        # Check if user chooses manual entry
        if user_input is not None and user_input["id"] == HUE_MANUAL_BRIDGE_ID:
            return await self.async_step_manual()

        if (
            user_input is not None
            and self.discovered_bridges is not None
            and user_input["id"] in self.discovered_bridges
        ):
            self.bridge = self.discovered_bridges[user_input["id"]]
            await self.async_set_unique_id(self.bridge.id, raise_on_progress=False)
            return await self.async_step_link()

        # Find / discover bridges
        try:
            async with asyncio.timeout(5):
                bridges = await discover_nupnp(
                    websession=aiohttp_client.async_get_clientsession(self.hass)
                )
        except TimeoutError:
            bridges = []

        if bridges:
            # Find already configured hosts
            already_configured = self._async_current_ids(False)
            bridges = [
                bridge for bridge in bridges if bridge.id not in already_configured
            ]
            self.discovered_bridges = {bridge.id: bridge for bridge in bridges}

        if not self.discovered_bridges:
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("id"): vol.In(
                        {
                            **{bridge.id: bridge.host for bridge in bridges},
                            HUE_MANUAL_BRIDGE_ID: "Manually add a Hue Bridge",
                        }
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual bridge setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            )

        self._async_abort_entries_match({"host": user_input["host"]})
        if (bridge := await self._get_bridge(user_input[CONF_HOST])) is None:
            return self.async_abort(reason="cannot_connect")
        self.bridge = bridge
        return await self.async_step_link()

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to link with the Hue bridge.

        Given a configured host, will ask the user to press the link button
        to connect to the bridge.
        """
        if user_input is None:
            return self.async_show_form(step_id="link")

        bridge = self.bridge
        assert bridge is not None
        errors = {}
        device_name = unicode_slug.slugify(
            self.hass.config.location_name, max_length=19
        )

        try:
            app_key = await create_app_key(
                bridge.host,
                f"home-assistant#{device_name}",
                websession=aiohttp_client.async_get_clientsession(self.hass),
            )
        except LinkButtonNotPressed:
            errors["base"] = "register_failed"
        except CannotConnect:
            LOGGER.error("Error connecting to the Hue bridge at %s", bridge.host)
            return self.async_abort(reason="cannot_connect")
        except Exception:
            LOGGER.exception(
                "Unknown error connecting with Hue bridge at %s", bridge.host
            )
            errors["base"] = "linking"

        if errors:
            return self.async_show_form(step_id="link", errors=errors)

        # Can happen if we come from import or manual entry
        if self.unique_id is None:
            await self.async_set_unique_id(
                normalize_bridge_id(bridge.id), raise_on_progress=False
            )

        return self.async_create_entry(
            title=f"Hue Bridge {bridge.id}",
            data={
                CONF_HOST: bridge.host,
                CONF_API_KEY: app_key,
                CONF_API_VERSION: 2 if bridge.supports_v2 else 1,
            },
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Hue bridge.

        This flow is triggered by the Zeroconf component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # Ignore if host is IPv6
        if discovery_info.ip_address.version == 6:
            return self.async_abort(reason="invalid_host")

        # abort if we already have exactly this bridge id/host
        # reload the integration if the host got updated
        bridge_id = normalize_bridge_id(discovery_info.properties["bridgeid"])
        await self.async_set_unique_id(bridge_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info.host}, reload_on_update=True
        )

        # we need to query the other capabilities too
        bridge = await self._get_bridge(
            discovery_info.host, discovery_info.properties["bridgeid"]
        )
        if bridge is None:
            return self.async_abort(reason="cannot_connect")
        self.bridge = bridge
        return await self.async_step_link()

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Hue bridge on HomeKit.

        The bridge ID communicated over HomeKit differs, so we cannot use that
        as the unique identifier. Therefore, this method uses discovery without
        a unique ID.
        """
        bridge = await self._get_bridge(discovery_info.host)
        if bridge is None:
            return self.async_abort(reason="cannot_connect")
        self.bridge = bridge
        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_link()

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a new bridge as a config entry.

        This flow is triggered by `async_setup` for both configured and
        discovered bridges. Triggered for any bridge that does not have a
        config entry yet (based on host).

        This flow is also triggered by `async_step_discovery`.
        """
        # Check if host exists, abort if so.
        self._async_abort_entries_match({"host": import_data["host"]})

        bridge = await self._get_bridge(import_data["host"])
        if bridge is None:
            return self.async_abort(reason="cannot_connect")
        self.bridge = bridge
        return await self.async_step_link()


class HueV1OptionsFlowHandler(OptionsFlow):
    """Handle Hue options for V1 implementation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Hue options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ALLOW_HUE_GROUPS,
                        default=self.config_entry.options.get(
                            CONF_ALLOW_HUE_GROUPS, DEFAULT_ALLOW_HUE_GROUPS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_ALLOW_UNREACHABLE,
                        default=self.config_entry.options.get(
                            CONF_ALLOW_UNREACHABLE, DEFAULT_ALLOW_UNREACHABLE
                        ),
                    ): bool,
                }
            ),
        )


class HueV2OptionsFlowHandler(OptionsFlow):
    """Handle Hue options for V2 implementation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Hue options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # create a list of Hue device ID's that the user can select
        # to ignore availability status
        dev_reg = dr.async_get(self.hass)
        entries = dr.async_entries_for_config_entry(dev_reg, self.config_entry.entry_id)
        dev_ids = {
            identifier[1]: entry.name
            for entry in entries
            for identifier in entry.identifiers
            if identifier[0] == DOMAIN
        }
        # filter any non existing device id's from the list
        cur_ids = [
            item
            for item in self.config_entry.options.get(CONF_IGNORE_AVAILABILITY, [])
            if item in dev_ids
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_IGNORE_AVAILABILITY,
                        default=cur_ids,
                    ): cv.multi_select(dev_ids),
                }
            ),
        )
