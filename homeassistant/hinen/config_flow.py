"""Config flow for YouTube integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CHANNEL_CREATION_HELP_URL, CONF_DEVICES, DOMAIN, HOST, LOGGER
from .hinen import HinenOpen
from .hinen_exception import ForbiddenError


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google OAuth2 authentication."""

    _data: dict[str, Any] = {}
    _title: str = ""

    DOMAIN = DOMAIN

    _hinen_open: HinenOpen | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HinenOpenFlowHandler:
        """Get the options flow for this handler."""
        return HinenOpenFlowHandler()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

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
            if not device_infos:
                return self.async_abort(
                    reason="no_device",
                    description_placeholders={"support_url": CHANNEL_CREATION_HELP_URL},
                )
        except ForbiddenError as ex:
            error = ex.args[0]
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": error},
            )
        except Exception as ex:  # noqa: BLE001
            LOGGER.error("Unknown error occurred: %s", ex.args)
            return self.async_abort(reason="unknown")
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

        # Get user's own devices
        device_infos = [
            device_info async for device_info in hinen_open.get_device_infos()
        ]
        if not device_infos:
            return self.async_abort(
                reason="no_device",
                description_placeholders={"support_url": CHANNEL_CREATION_HELP_URL},
            )

        # Start with user's device
        selectable_devices = [
            SelectOptionDict(
                value=str(device_info.id),
                label=f"{device_info.device_name},{device_info.serial_number} (Your Device)",
            )
            for device_info in device_infos
        ]

        # # Add subscribed channels
        # selectable_devices.extend(
        #     [
        #         SelectOptionDict(
        #             value=subscription.snippet.channel_id,
        #             label=subscription.snippet.title,
        #         )
        #         async for subscription in youtube.get_user_subscriptions()
        #     ]
        # )

        if not selectable_devices:
            return self.async_abort(reason="no_device")
        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICES): SelectSelector(
                        SelectSelectorConfig(options=selectable_devices, multiple=True)
                    ),
                }
            ),
        )


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
        async_get_clientsession(self.hass)
        hinen_open = HinenOpen()
        await hinen_open.set_user_authentication(
            self.config_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )

        # Get user's own devices
        device_infos = [
            device_info async for device_info in hinen_open.get_device_infos()
        ]
        if not device_infos:
            return self.async_abort(
                reason="no_device",
                description_placeholders={"support_url": CHANNEL_CREATION_HELP_URL},
            )

        # Start with user's own channels
        selectable_devices = [
            SelectOptionDict(
                value=str(device_info.id),
                label=f"{device_info.device_name},{device_info.serial_number} (Your Device)",
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
