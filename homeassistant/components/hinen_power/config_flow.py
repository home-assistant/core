"""Config flow for Hinen Power integration."""

from __future__ import annotations

import logging
from typing import Any

from hinen_open_api import HinenOpen, HinenPublic
from hinen_open_api.exceptions import ForbiddenError, HinenAPIError
import voluptuous as vol

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from . import application_credentials
from .const import (
    ATTR_AUTH_LANGUAGE,
    ATTR_REGION_CODE,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICES,
    DOMAIN,
    HOST,
    LOGGER,
    SUPPORTED_LANGUAGES,
)
from .coordinator import HinenPowerConfigEntry


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle hinen OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the flow handler."""
        super().__init__()
        self._data: dict[str, Any] = {}
        self._title: str = ""
        self._hinen_open: HinenOpen | None = None
        self._language: str | None = None
        self._region_code: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: HinenPowerConfigEntry,
    ) -> HinenOpenFlowHandler:
        """Get the options flow for this handler."""
        return HinenOpenFlowHandler()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow start."""
        if user_input is not None:
            self._language = user_input[ATTR_AUTH_LANGUAGE]
            self._region_code = user_input[ATTR_REGION_CODE]
            credential: ClientCredential = ClientCredential(
                user_input[CONF_CLIENT_ID], user_input[CONF_CLIENT_SECRET]
            )

            self.flow_impl = (
                await application_credentials.async_get_auth_implementation(
                    self.hass,
                    DOMAIN,
                    credential,
                    language=self._language,
                    region_code=self._region_code,
                )
            )
            config_entry_oauth2_flow.async_register_implementation(
                self.hass, DOMAIN, self.flow_impl
            )
            return await super().async_step_auth()

        default_language = SUPPORTED_LANGUAGES[0][0]

        try:
            country_codes = await self._get_country_list()
        except HinenAPIError as ex:
            LOGGER.error("Failed to fetch country list: %s", ex)
            return self.async_abort(reason="failed_to_fetch_countries")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_AUTH_LANGUAGE, default=default_language): vol.In(
                        dict(SUPPORTED_LANGUAGES)
                    ),
                    vol.Required(ATTR_REGION_CODE): CountrySelector(
                        CountrySelectorConfig(countries=country_codes)
                    ),
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
        )

    async def get_resource(self, token: str, host: str) -> HinenOpen:
        """Get Hinen Open resource async."""
        if self._hinen_open is None:
            self._hinen_open = HinenOpen(
                host, session=async_get_clientsession(self.hass)
            )
            await self._hinen_open.set_user_authentication(token)
        return self._hinen_open

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        try:
            hinen_open = await self.get_resource(
                data[CONF_TOKEN][CONF_ACCESS_TOKEN], data[CONF_TOKEN][HOST]
            )
            device_infos = [
                device_info async for device_info in hinen_open.get_device_infos()
            ]

        except ForbiddenError as ex:
            error = ex.args[0]
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": error},
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unknown error occurred")
            return self.async_abort(reason="unknown")

        if not device_infos:
            return self.async_abort(reason="no_device")

        self._title = device_infos[0].device_name
        self._data = data

        await self.async_set_unique_id(str(device_infos[0].id))
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

            return await self.async_step_devices()

        self._abort_if_unique_id_mismatch(
            reason="wrong_account",
            description_placeholders={"title": self._title},
        )

        return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select which device info to track."""
        if user_input:
            return self.async_create_entry(
                title=self._title,
                data=self._data,
                options=user_input,
            )
        hinen_open = await self.get_resource(
            self._data[CONF_TOKEN][CONF_ACCESS_TOKEN], self._data[CONF_TOKEN][HOST]
        )

        device_infos = [
            device_info async for device_info in hinen_open.get_device_infos()
        ]

        selectable_devices = [
            SelectOptionDict(
                value=str(device_info.id),
                label=f"{device_info.device_name},{device_info.serial_number}",
            )
            for device_info in device_infos
        ]

        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICES): vol.All(
                        SelectSelector(
                            SelectSelectorConfig(
                                options=selectable_devices, multiple=True
                            )
                        ),
                        vol.Length(min=1),
                    )
                }
            ),
        )

    async def _get_country_list(self) -> list[str]:
        """Fetch the list of countries."""
        hinen_public = HinenPublic(session=async_get_clientsession(self.hass))
        countries = await hinen_public.get_country_list()
        return [country["code"] for country in countries]


class HinenOpenFlowHandler(OptionsFlow):
    """Hinen Open Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initialize form."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title,
                data=user_input,
            )

        hinen_open = HinenOpen(
            self.config_entry.data[CONF_TOKEN][HOST],
            session=async_get_clientsession(self.hass),
        )
        await hinen_open.set_user_authentication(
            self.config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN],
            self.config_entry.data[CONF_TOKEN]["refresh_token"],
        )

        # Get user's own devices
        device_infos = [
            device_info async for device_info in hinen_open.get_device_infos()
        ]
        if not device_infos:
            return self.async_abort(
                reason="no_device",
            )

        # Start with user's own channels
        selectable_devices = [
            SelectOptionDict(
                value=str(device_info.id),
                label=f"{device_info.device_name},{device_info.serial_number}",
            )
            for device_info in device_infos
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_DEVICES): SelectSelector(
                            SelectSelectorConfig(
                                options=selectable_devices, multiple=True
                            )
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
