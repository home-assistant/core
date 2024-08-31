"""Config flow for bluesound."""

import logging
from typing import Any

from pyblu import Player, SyncStatus
from pyblu.errors import PlayerUnreachableError
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .media_player import DEFAULT_PORT
from .utils import format_unique_id

_LOGGER = logging.getLogger(__name__)


class BluesoundConfigFlow(ConfigFlow, domain=DOMAIN):
    """Bluesound config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._port = DEFAULT_PORT
        self._sync_status: SyncStatus | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            async with Player(
                user_input[CONF_HOST], user_input[CONF_PORT], session=session
            ) as player:
                try:
                    sync_status = await player.sync_status(timeout=1)
                except PlayerUnreachableError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(
                        format_unique_id(sync_status.mac, user_input[CONF_PORT])
                    )
                    self._abort_if_unique_id_configured(
                        updates={
                            CONF_HOST: user_input[CONF_HOST],
                        }
                    )

                    return self.async_create_entry(
                        title=sync_status.name,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=11000): int,
                }
            ),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import bluesound config entry from configuration.yaml."""
        session = async_get_clientsession(self.hass)
        async with Player(
            import_data[CONF_HOST], import_data[CONF_PORT], session=session
        ) as player:
            try:
                sync_status = await player.sync_status(timeout=1)
            except PlayerUnreachableError:
                return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(
            format_unique_id(sync_status.mac, import_data[CONF_PORT])
        )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=sync_status.name,
            data=import_data,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        if discovery_info.port is not None:
            self._port = discovery_info.port

        session = async_get_clientsession(self.hass)
        try:
            async with Player(
                discovery_info.host, self._port, session=session
            ) as player:
                sync_status = await player.sync_status(timeout=1)
        except PlayerUnreachableError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(format_unique_id(sync_status.mac, self._port))

        self._host = discovery_info.host
        self._sync_status = sync_status

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
            }
        )

        self.context.update(
            {
                "title_placeholders": {"name": sync_status.name},
                "configuration_url": f"http://{discovery_info.host}",
            }
        )
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the zeroconf setup."""
        assert self._sync_status is not None
        assert self._host is not None

        if user_input is not None:
            return self.async_create_entry(
                title=self._sync_status.name,
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                },
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._sync_status.name,
                "host": self._host,
            },
        )
