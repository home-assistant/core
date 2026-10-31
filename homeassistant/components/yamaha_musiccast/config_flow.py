"""Config flow for MusicCast."""

import logging
from typing import Any, override
from urllib.parse import urlparse

from aiohttp import ClientConnectorError, DummyCookieJar
from aiomusiccast import MusicCastConnectionException, MusicCastDevice
import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from . import get_upnp_desc
from .const import (
    CONF_DISPLAYED_SOURCES,
    CONF_HIDDEN_SOURCES,
    CONF_SERIAL,
    CONF_UPNP_DESC,
    DOMAIN,
)
from .entity import get_source_label

_LOGGER = logging.getLogger(__name__)


class MusicCastFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a MusicCast config flow."""

    VERSION = 1

    serial_number: str | None = None
    host: str
    upnp_description: str | None = None

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MusicCastOptionsFlowHandler:
        """Get the options flow for this handler."""
        return MusicCastOptionsFlowHandler()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        # Request user input, unless we are preparing discovery flow
        if user_input is None:
            return self._show_setup_form()

        host = user_input[CONF_HOST]
        serial_number = None

        errors = {}
        # Check if device is a MusicCast device

        try:
            info = await MusicCastDevice.get_device_info(
                host, async_create_clientsession(self.hass, cookie_jar=DummyCookieJar())
            )
        except MusicCastConnectionException, ClientConnectorError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if (serial_number := info.get("system_id")) is None:
                errors["base"] = "no_musiccast_device"

        if not errors:
            await self.async_set_unique_id(serial_number, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=host,
                data={
                    CONF_HOST: host,
                    CONF_SERIAL: serial_number,
                    CONF_UPNP_DESC: await get_upnp_desc(self.hass, host),
                },
            )

        return self._show_setup_form(errors)

    def _show_setup_form(self, errors: dict | None = None) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema({probatio.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    @override
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle ssdp discoveries."""
        if not await MusicCastDevice.check_yamaha_ssdp(
            discovery_info.ssdp_location,
            async_create_clientsession(self.hass, cookie_jar=DummyCookieJar()),
        ):
            return self.async_abort(reason="yxc_control_url_missing")

        self.serial_number = discovery_info.upnp[ATTR_UPNP_SERIAL]
        self.upnp_description = discovery_info.ssdp_location

        # ssdp_location and hostname have been checked in
        # check_yamaha_ssdp so it is safe to ignore type
        self.host = urlparse(discovery_info.ssdp_location).hostname  # type: ignore[assignment]

        await self.async_set_unique_id(self.serial_number)
        self._abort_if_unique_id_configured(
            {
                CONF_HOST: self.host,
                CONF_UPNP_DESC: self.upnp_description,
            }
        )
        self.context.update(
            {
                "title_placeholders": {
                    "name": discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME, self.host)
                }
            }
        )

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.host,
                data={
                    CONF_HOST: self.host,
                    CONF_SERIAL: self.serial_number,
                    CONF_UPNP_DESC: self.upnp_description,
                },
            )

        return self.async_show_form(step_id="confirm")


class MusicCastOptionsFlowHandler(OptionsFlow):
    """Handle MusicCast options."""

    _offered_source_ids: list[str]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage which sources are displayed."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            displayed_sources = user_input[CONF_DISPLAYED_SOURCES]
            hidden_sources = [
                source_id
                for source_id in self._offered_source_ids
                if source_id not in displayed_sources
            ]
            return self.async_create_entry(data={CONF_HIDDEN_SOURCES: hidden_sources})

        coordinator = self.config_entry.runtime_data

        source_labels: dict[str, str] = {}
        for zone in coordinator.data.zones.values():
            for inp in zone.input_list:
                source_labels.setdefault(
                    inp,
                    get_source_label(
                        coordinator.data.input_names, zone.input_list, inp
                    ),
                )
        self._offered_source_ids = list(source_labels)

        hidden_sources = self.config_entry.options.get(CONF_HIDDEN_SOURCES, [])

        source_options = [
            selector.SelectOptionDict(value=source_id, label=label)
            for source_id, label in sorted(
                source_labels.items(), key=lambda item: item[1]
            )
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_DISPLAYED_SOURCES,
                        default=[
                            source_id
                            for source_id in source_labels
                            if source_id not in hidden_sources
                        ],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=source_options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )
