"""Config flow for Lutron Caseta."""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
from typing import Any

from pylutron_caseta.pairing import PAIR_CA, PAIR_CERT, PAIR_KEY, async_pair
from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .const import (
    ABORT_REASON_CANNOT_CONNECT,
    BRIDGE_DEVICE_ID,
    BRIDGE_TIMEOUT,
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    STEP_IMPORT_FAILED,
)

HOSTNAME = "hostname"


FILE_MAPPING = {
    PAIR_KEY: CONF_KEYFILE,
    PAIR_CERT: CONF_CERTFILE,
    PAIR_CA: CONF_CA_CERTS,
}

_LOGGER = logging.getLogger(__name__)

ENTRY_DEFAULT_TITLE = "Caséta bridge"

DATA_SCHEMA_USER = vol.Schema({vol.Required(CONF_HOST): str})
TLS_ASSET_TEMPLATE = "lutron_caseta-{}-{}.pem"


class LutronCasetaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Lutron Caseta config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize a Lutron Caseta flow."""
        self.data: dict[str, Any] = {}
        self.lutron_id: str | None = None
        self.tls_assets_validated = False
        self.attempted_tls_validation = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.data[CONF_HOST] = user_input[CONF_HOST]
            return await self.async_step_link()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA_USER)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        hostname = discovery_info.hostname
        if hostname is None or not hostname.lower().startswith("lutron-"):
            return self.async_abort(reason="not_lutron_device")

        self.lutron_id = hostname.split("-")[1].replace(".local.", "")

        await self.async_set_unique_id(self.lutron_id)
        host = discovery_info.host
        self._abort_if_unique_id_configured({CONF_HOST: host})

        self.data[CONF_HOST] = host
        self.context["title_placeholders"] = {
            CONF_NAME: self.bridge_id,
            CONF_HOST: host,
        }
        return await self.async_step_link()

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by homekit discovery."""
        return await self.async_step_zeroconf(discovery_info)

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle pairing with the hub."""
        errors = {}
        # Abort if existing entry with matching host exists.
        self._async_abort_entries_match({CONF_HOST: self.data[CONF_HOST]})

        self._configure_tls_assets()

        if (
            not self.attempted_tls_validation
            and await self.hass.async_add_executor_job(self._tls_assets_exist)
            and await self.async_get_lutron_id()
        ):
            self.tls_assets_validated = True
        self.attempted_tls_validation = True

        if user_input is not None:
            if self.tls_assets_validated:
                # If we previous paired and the tls assets already exist,
                # we do not need to go though pairing again.
                return self.async_create_entry(title=self.bridge_id, data=self.data)

            assets = None
            try:
                assets = await async_pair(self.data[CONF_HOST])
            except (TimeoutError, OSError):
                errors["base"] = "cannot_connect"

            if not errors:
                await self.hass.async_add_executor_job(self._write_tls_assets, assets)
                return self.async_create_entry(title=self.bridge_id, data=self.data)

        return self.async_show_form(
            step_id="link",
            errors=errors,
            description_placeholders={
                CONF_NAME: self.bridge_id,
                CONF_HOST: self.data[CONF_HOST],
            },
        )

    @property
    def bridge_id(self):
        """Return the best identifier for the bridge.

        If the bridge was not discovered via zeroconf,
        we fallback to using the host.
        """
        return self.lutron_id or self.data[CONF_HOST]

    def _write_tls_assets(self, assets):
        """Write the tls assets to disk."""
        for asset_key, conf_key in FILE_MAPPING.items():
            with open(
                self.hass.config.path(self.data[conf_key]), "w", encoding="utf8"
            ) as file_handle:
                file_handle.write(assets[asset_key])

    def _tls_assets_exist(self):
        """Check to see if tls assets are already on disk."""
        for conf_key in FILE_MAPPING.values():
            if not os.path.exists(self.hass.config.path(self.data[conf_key])):
                return False
        return True

    @callback
    def _configure_tls_assets(self):
        """Fill the tls asset locations in self.data."""
        for asset_key, conf_key in FILE_MAPPING.items():
            self.data[conf_key] = TLS_ASSET_TEMPLATE.format(self.bridge_id, asset_key)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a new Caseta bridge as a config entry.

        This flow is triggered by `async_setup`.
        """
        host = import_data[CONF_HOST]
        # Store the imported config for other steps in this flow to access.
        self.data[CONF_HOST] = host

        # Abort if existing entry with matching host exists.
        self._async_abort_entries_match({CONF_HOST: self.data[CONF_HOST]})

        self.data[CONF_KEYFILE] = import_data[CONF_KEYFILE]
        self.data[CONF_CERTFILE] = import_data[CONF_CERTFILE]
        self.data[CONF_CA_CERTS] = import_data[CONF_CA_CERTS]

        if not (lutron_id := await self.async_get_lutron_id()):
            # Ultimately we won't have a dedicated step for import failure, but
            # in order to keep configuration.yaml-based configs transparently
            # working without requiring further actions from the user, we don't
            # display a form at all before creating a config entry in the
            # default case, so we're only going to show a form in case the
            # import fails.
            # This will change in an upcoming release where UI-based config flow
            # will become the default for the Lutron Caseta integration (which
            # will require users to go through a confirmation flow for imports).
            return await self.async_step_import_failed()

        await self.async_set_unique_id(lutron_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=ENTRY_DEFAULT_TITLE, data=self.data)

    async def async_step_import_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Make failed import surfaced to user."""
        self.context["title_placeholders"] = {CONF_NAME: self.data[CONF_HOST]}

        if user_input is None:
            return self.async_show_form(
                step_id=STEP_IMPORT_FAILED,
                description_placeholders={"host": self.data[CONF_HOST]},
                errors={"base": ERROR_CANNOT_CONNECT},
            )

        return self.async_abort(reason=ABORT_REASON_CANNOT_CONNECT)

    async def async_get_lutron_id(self) -> str | None:
        """Check if we can connect to the bridge with the current config."""
        try:
            bridge = Smartbridge.create_tls(
                hostname=self.data[CONF_HOST],
                keyfile=self.hass.config.path(self.data[CONF_KEYFILE]),
                certfile=self.hass.config.path(self.data[CONF_CERTFILE]),
                ca_certs=self.hass.config.path(self.data[CONF_CA_CERTS]),
            )
        except ssl.SSLError:
            _LOGGER.error(
                "Invalid certificate used to connect to bridge at %s",
                self.data[CONF_HOST],
            )
            return None

        try:
            async with asyncio.timeout(BRIDGE_TIMEOUT):
                await bridge.connect()
        except TimeoutError:
            _LOGGER.error(
                "Timeout while trying to connect to bridge at %s",
                self.data[CONF_HOST],
            )
        else:
            if not bridge.is_connected():
                return None
            devices = bridge.get_devices()
            bridge_device = devices[BRIDGE_DEVICE_ID]
            return hex(bridge_device["serial"])[2:].zfill(8)
        finally:
            await bridge.close()

        return None
