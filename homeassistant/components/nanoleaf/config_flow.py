"""Config flow for Nanoleaf integration."""
from __future__ import annotations

import logging
from typing import Any, Final

from pynanoleaf import InvalidToken, Nanoleaf, NotAuthorizingNewTokens, Unavailable
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.util.json import load_json, save_json

from .const import DOMAIN
from .util import pynanoleaf_get_info

_LOGGER = logging.getLogger(__name__)

# For discovery integration import
CONFIG_FILE: Final = ".nanoleaf.conf"

USER_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Nanoleaf config flow."""

    VERSION = 1

    nanoleaf: Nanoleaf

    # For discovery integration import
    discovery_conf: dict
    device_id: str

    def __init__(self) -> None:
        """Initialize a Nanoleaf flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Nanoleaf flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=USER_SCHEMA, last_step=False
            )
        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        self.nanoleaf = Nanoleaf(user_input[CONF_HOST])
        try:
            await self.hass.async_add_executor_job(self.nanoleaf.authorize)
        except Unavailable:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                errors={"base": "cannot_connect"},
                last_step=False,
            )
        except NotAuthorizingNewTokens:
            pass
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error connecting to Nanoleaf")
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                last_step=False,
                errors={"base": "unknown"},
            )
        return self.async_show_form(step_id="link")

    async def async_step_zeroconf(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle Nanoleaf Zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovered: %s", discovery_info)
        return await self._async_discovery_handler(discovery_info)

    async def async_step_homekit(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle Nanoleaf Homekit discovery."""
        _LOGGER.debug("Homekit discovered: %s", discovery_info)
        return await self._async_discovery_handler(discovery_info)

    async def _async_discovery_handler(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle Nanoleaf discovery."""
        host = discovery_info["host"]
        name = discovery_info["name"].replace(f".{discovery_info['type']}", "")
        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured({CONF_HOST: host})
        self.nanoleaf = Nanoleaf(host)

        # Import from discovery integration
        self.device_id = discovery_info["properties"]["id"]
        self.discovery_conf = dict(load_json(self.hass.config.path(CONFIG_FILE)))
        self.nanoleaf.token = self.discovery_conf.get(host, {}).get("token")  # < 2021.4
        self.nanoleaf.token = self.discovery_conf.get(self.device_id, {}).get(
            "token", self.nanoleaf.token
        )  # >= 2021.4
        if self.nanoleaf.token is not None:
            self.context["source"] = config_entries.SOURCE_INTEGRATION_DISCOVERY
            _LOGGER.warning(
                "Importing Nanoleaf %s from the discovery integration", name
            )
            return await self.async_setup_finish()

        self.context["title_placeholders"] = {"name": name}
        return self.async_show_form(step_id="link")

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Nanoleaf link step."""
        if user_input is None:
            return self.async_show_form(step_id="link")

        try:
            await self.hass.async_add_executor_job(self.nanoleaf.authorize)
        except NotAuthorizingNewTokens:
            return self.async_show_form(
                step_id="link", errors={"base": "not_allowing_new_tokens"}
            )
        except Unavailable:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                errors={"base": "cannot_connect"},
                last_step=False,
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error authorizing Nanoleaf")
            return self.async_show_form(step_id="link", errors={"base": "unknown"})
        return await self.async_setup_finish()

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle Nanoleaf configuration import."""
        self._async_abort_entries_match({CONF_HOST: config[CONF_HOST]})
        _LOGGER.debug(
            "Importing Nanoleaf on %s from your configuration.yaml", config[CONF_HOST]
        )
        self.nanoleaf = Nanoleaf(config[CONF_HOST])
        self.nanoleaf.token = config[CONF_TOKEN]
        return await self.async_setup_finish()

    async def async_setup_finish(self) -> FlowResult:
        """Finish Nanoleaf config flow."""
        try:
            info = await self.hass.async_add_executor_job(
                pynanoleaf_get_info, self.nanoleaf
            )
        except Unavailable:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                errors={"base": "cannot_connect"},
                last_step=False,
            )
        except InvalidToken:
            return self.async_show_form(
                step_id="link", errors={"base": "invalid_token"}
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Nanoleaf at %s with token %s",
                self.nanoleaf.host,
                self.nanoleaf.token,
            )
            return self.async_show_form(
                step_id="user",
                data_schema=USER_SCHEMA,
                errors={"base": "unknown"},
                last_step=False,
            )
        name = info["name"]

        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured({CONF_HOST: self.nanoleaf.host})

        # Log successfully imported instructions and optionally update the Nanoleaf config file
        if self.context["source"] == config_entries.SOURCE_IMPORT:
            _LOGGER.warning(
                (
                    "Successfully imported Nanoleaf %s on %s.",
                    "You can remove the light from your configuration.yaml",
                ),
                name,
                self.nanoleaf.host,
            )
        elif self.context["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY:
            if self.nanoleaf.host in self.discovery_conf:
                self.discovery_conf.pop(self.nanoleaf.host)
            if self.device_id in self.discovery_conf:
                self.discovery_conf.pop(self.device_id)
            _LOGGER.warning(
                "Successfully imported Nanoleaf %s from the discovery integration",
                name,
            )
            if self.discovery_conf:
                save_json(self.hass.config.path(CONFIG_FILE), self.discovery_conf)
            else:
                save_json(
                    self.hass.config.path(CONFIG_FILE),
                    {
                        0: "The Nanoleaf configuration has been imported into a config flow.",
                        1: "This file is no longer used. YOU CAN DELETE THIS FILE.",
                        2: "If you used the discovery integration only for Nanoleaf you can remove it from your configuration.yaml",
                    },
                )
                _LOGGER.warning(
                    (
                        "All Nanoleaf devices from the discovery integration are imported. "
                        "You can remove the '%s' file from your config folder. (This file may be hidden.) "
                        "If you used the discovery integration only for Nanoleaf you can remove it from your configuration.yaml"
                    ),
                    CONFIG_FILE,
                )

        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: self.nanoleaf.host,
                CONF_TOKEN: self.nanoleaf.token,
            },
        )
