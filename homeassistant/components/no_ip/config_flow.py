"""Adds config flow for No-IP.com integration."""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import aiohttp
from aiohttp.hdrs import AUTHORIZATION, USER_AGENT
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DEFAULT_TIMEOUT,
    DOMAIN,
    HA_USER_AGENT,
    MANUFACTURER,
    NO_IP_ERRORS,
    UPDATE_URL,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = {
    vol.Required(CONF_DOMAIN): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
    vol.Required(CONF_USERNAME): TextSelector(
        TextSelectorConfig(type=TextSelectorType.TEXT)
    ),
    vol.Required(CONF_PASSWORD): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
}


async def async_validate_no_ip(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Update No-IP.com."""
    no_ip_domain = user_input[CONF_DOMAIN]
    user = user_input[CONF_USERNAME]
    password = user_input[CONF_PASSWORD]

    auth_str = base64.b64encode(f"{user}:{password}".encode())

    session = aiohttp_client.async_create_clientsession(hass)
    params = {"hostname": no_ip_domain}

    headers = {
        AUTHORIZATION: f"Basic {auth_str.decode('utf-8')}",
        USER_AGENT: HA_USER_AGENT,
    }

    try:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await session.get(
                UPDATE_URL, params=params, headers=headers, raise_for_status=True
            )
            body = (await resp.text()).strip()
            if resp.status == 200 and (
                body.startswith("good") or body.startswith("nochg")
            ):
                ipAddress = body.split(" ")[1]
                return {"title": MANUFACTURER, CONF_IP_ADDRESS: ipAddress}
            no_ip_error = "unknown"
            if body in NO_IP_ERRORS:
                no_ip_error = NO_IP_ERRORS[body]
            return {"title": MANUFACTURER, "exception": no_ip_error}
    except (aiohttp.ClientError, aiohttp.ClientResponseError) as client_error:
        _LOGGER.warning("Unable to connect to No-IP.com API: %s", client_error)
        raise
    except asyncio.TimeoutError:
        _LOGGER.warning("Timeout from No-IP.com API for domain: %s", no_ip_domain)
        raise
    except Exception as error:  # pylint: disable=broad-except
        _LOGGER.error("Error updating data from No-IP.com: %s", error)
        raise


class NoIPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for No-IP.com integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        result = None

        if user_input is not None:
            try:
                result = await async_validate_no_ip(self.hass, user_input)
                if "exception" not in result:
                    return self.async_create_entry(
                        title=result["title"],
                        data={
                            CONF_DOMAIN: user_input[CONF_DOMAIN],
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
                errors["base"] = result["exception"]
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA), errors=errors
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import No-IP.com config from configuration.yaml."""
        # Check if imported data is available
        if not import_data:
            async_delete_issue(self.hass, DOMAIN, "deprecated_yaml")
            return await self.async_step_user()
        # Create an issue for the deprecated YAML configuration and display a warning
        async_create_issue(
            self.hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2024.6.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )
        # Check if there is already a configuration entry with the same domain and username
        self._async_abort_entries_match(
            {
                CONF_DOMAIN: import_data[CONF_DOMAIN],
                CONF_USERNAME: import_data[CONF_USERNAME],
            }
        )
        # Validate the imported data using async_validate_no_ip
        result = await async_validate_no_ip(self.hass, import_data)
        # Check if there is no exception
        if "exception" not in result:
            _LOGGER.debug(
                "Starting import of sensor from configuration.yaml (deprecated) - %s",
                import_data,
            )
            # Process the imported configuration data further
            return await self.async_step_user(import_data)
        # Display a warning that no configuration can be imported
        _LOGGER.debug(
            "No configuration (%s) to import. %s", import_data, result["exception"]
        )
        return self.async_abort(reason="No configuration to import.")
