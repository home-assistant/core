"""Config flow for OPNsense integration."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from http import HTTPStatus
import logging
import re
from typing import Any
from urllib.parse import urlparse

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
from requests import RequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    CLIENT_TIMEOUT,
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACES,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    INTEGRATION_TITLE,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Normalize and validate the configured OPNsense base URL."""
    fixed_url = url.strip()
    parsed = urlparse(fixed_url)

    if not parsed.scheme and not parsed.netloc:
        fixed_url = f"https://{fixed_url}"
        parsed = urlparse(fixed_url)

    if not parsed.netloc:
        raise InvalidURL

    # Keep behavior stable for unique IDs by stripping path/query/fragment
    # and lowercasing netloc for canonical matching.
    return parsed._replace(
        netloc=parsed.netloc.lower(),
        path="",
        params="",
        query="",
        fragment="",
    ).geturl()


def _title_from_url(url: str) -> str:
    """Create an entry title from URL."""
    parsed = urlparse(url)
    return parsed.hostname or INTEGRATION_TITLE


def _normalize_tracker_interfaces(value: Any) -> list[str]:
    """Normalize configured tracker interfaces from string/list input."""
    if isinstance(value, list):
        normalized = [
            item.strip() for item in value if isinstance(item, str) and item.strip()
        ]
        return list(dict.fromkeys(normalized))

    if not isinstance(value, str):
        return []

    normalized = [
        item.strip()
        for item in re.split(r"[,\n]+", value)
        if isinstance(item, str) and item.strip()
    ]
    return list(dict.fromkeys(normalized))


def _tracker_interfaces_default(user_input: Mapping[str, Any] | None) -> str:
    """Build default text value for tracker interfaces field."""
    if not user_input:
        return ""

    value = user_input.get(CONF_TRACKER_INTERFACES, "")
    if isinstance(value, list):
        return ", ".join(item for item in value if isinstance(item, str))
    return value if isinstance(value, str) else ""


def _build_user_schema(user_input: Mapping[str, Any] | None = None) -> vol.Schema:
    """Build user step schema."""
    if not user_input:
        user_input = {}

    return vol.Schema(
        {
            # Allow scheme-less host input; _normalize_url will validate and
            # canonicalize it (including inferring https:// when missing).
            vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): cv.string,
            vol.Required(
                CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
            ): cv.string,
            vol.Required(
                CONF_API_SECRET, default=user_input.get(CONF_API_SECRET, "")
            ): cv.string,
            vol.Optional(
                CONF_VERIFY_SSL,
                default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): cv.boolean,
            vol.Optional(
                CONF_TRACKER_INTERFACES,
                default=_tracker_interfaces_default(user_input),
            ): cv.string,
        }
    )


async def _async_validate_input(
    hass: HomeAssistant, user_input: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate credentials and normalize data."""

    data = dict(user_input)

    data[CONF_URL] = _normalize_url(user_input[CONF_URL])

    data[CONF_TRACKER_INTERFACES] = _normalize_tracker_interfaces(
        user_input.get(CONF_TRACKER_INTERFACES)
    )

    client = diagnostics.InterfaceClient(
        data[CONF_API_KEY],
        data[CONF_API_SECRET],
        data[CONF_URL],
        data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        timeout=CLIENT_TIMEOUT,
    )

    try:
        await hass.async_add_executor_job(client.get_arp)
    except APIException as err:
        if err.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            _LOGGER.debug("Authentication failed while validating OPNsense credentials")
            raise InvalidAuth from err
        _LOGGER.debug("Failed to validate OPNsense credentials", exc_info=err)
        raise CannotConnect from err
    except RequestException as err:
        _LOGGER.debug("Failed to validate OPNsense credentials", exc_info=err)
        raise CannotConnect from err

    tracker_interfaces: list[str] = data[CONF_TRACKER_INTERFACES]
    if tracker_interfaces:
        netinsight_client = diagnostics.NetworkInsightClient(
            data[CONF_API_KEY],
            data[CONF_API_SECRET],
            data[CONF_URL],
            data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            timeout=CLIENT_TIMEOUT,
        )

        try:
            interfaces = await hass.async_add_executor_job(
                lambda: list(netinsight_client.get_interfaces().values())
            )
        except APIException as err:
            if err.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
                _LOGGER.debug(
                    "Authentication failed while validating OPNsense tracker interfaces"
                )
                raise InvalidAuth from err
            _LOGGER.debug(
                "Failed to validate OPNsense tracker interfaces", exc_info=err
            )
            raise CannotConnect from err
        except RequestException as err:
            _LOGGER.debug(
                "Failed to validate OPNsense tracker interfaces", exc_info=err
            )
            raise CannotConnect from err

        for interface in tracker_interfaces:
            if interface not in interfaces:
                raise InvalidTrackerInterface

    return data


class OPNsenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an OPNsense config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                data = await _async_validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidTrackerInterface:
                errors["base"] = "invalid_tracker_interface"
            except InvalidURL:
                errors["base"] = "invalid_url"
            except Exception:  # pragma: no cover - defensive fallback
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(_normalize_url(data[CONF_URL]))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=_title_from_url(data[CONF_URL]),
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(user_input),
            errors=errors,
        )

    async def async_step_import(
        self, user_input: MutableMapping[str, Any]
    ) -> ConfigFlowResult:
        """Import from configuration.yaml."""
        validated_data = await _async_validate_input(self.hass, user_input)

        await self.async_set_unique_id(_normalize_url(validated_data[CONF_URL]))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=_title_from_url(validated_data[CONF_URL]),
            data=validated_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            data = {
                **entry.data,
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_API_SECRET: user_input[CONF_API_SECRET],
            }

            try:
                validated_data = await _async_validate_input(self.hass, data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidTrackerInterface:
                errors["base"] = "invalid_tracker_interface"
            except InvalidURL:
                errors["base"] = "invalid_url"
            except Exception:  # pragma: no cover - defensive fallback
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(entry, data=validated_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): cv.string,
                    vol.Required(CONF_API_SECRET): cv.string,
                }
            ),
            errors=errors,
        )


class InvalidURL(Exception):
    """Error to indicate an invalid URL."""


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


class InvalidTrackerInterface(Exception):
    """Error to indicate configured tracker interface is invalid."""
