"""Config flow for INELNET Blinds integration."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from inelnet_api import InelnetChannel
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CHANNELS, DOMAIN


def parse_channels(value: str) -> list[int]:
    """Parse comma-separated channel string to list of positive ints."""
    if not value or not value.strip():
        raise ValueError("empty")
    parts = [p.strip() for p in value.split(",") if p.strip()]
    channels: list[int] = []
    for p in parts:
        try:
            ch = int(p)
        except ValueError as err:
            raise ValueError("invalid") from err
        if ch < 1:
            raise ValueError("out_of_range")
        if ch in channels:
            raise ValueError("duplicate")
        channels.append(ch)
    return sorted(channels)


def _is_valid_hostname(host: str) -> bool:
    """Validate hostname (not IP). Rejects dotted-quad that failed as IP (e.g. 256.1.1.1)."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        return False
    if len(host) > 253:
        return False
    label_re = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
    labels = host.split(".")
    if not labels or any(not lb for lb in labels):
        return False
    for label in labels:
        if len(label) > 63 or not label_re.fullmatch(label):
            return False
    return True


def is_valid_host(host: str) -> bool:
    """Validate host as IPv4, IPv6, or hostname."""
    host = host.strip()
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return True
    return _is_valid_hostname(host)


class InelnetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for INELNET Blinds."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = (user_input.get(CONF_HOST) or "").strip()
            channels_str = (user_input.get(CONF_CHANNELS) or "").strip()

            if not is_valid_host(host):
                errors["base"] = "invalid_host"
            else:
                try:
                    channels = parse_channels(channels_str)
                except ValueError:
                    errors["base"] = "invalid_channels"
                else:
                    session = async_get_clientsession(self.hass)
                    client = InelnetChannel(host, channels[0])
                    try:
                        if await client.ping(session=session):
                            self._async_abort_entries_match({CONF_HOST: host})
                            await self.async_set_unique_id(host)
                            self._abort_if_unique_id_configured()

                            return self.async_create_entry(
                                title=f"INELNET {host} (ch "
                                f"{','.join(str(c) for c in channels)})",
                                data={
                                    CONF_HOST: host,
                                    CONF_CHANNELS: channels,
                                },
                            )
                        errors["base"] = "cannot_connect"
                    except TimeoutError, OSError:
                        errors["base"] = "cannot_connect"

        host_default = ""
        channels_default = "1"
        if user_input is not None:
            host_default = (user_input.get(CONF_HOST) or "").strip()
            ch_in = (user_input.get(CONF_CHANNELS) or "").strip()
            channels_default = ch_in or "1"
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=host_default): str,
                vol.Required(CONF_CHANNELS, default=channels_default): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> InelnetOptionsFlowHandler:
        """Return options flow handler for editing channels."""
        return InelnetOptionsFlowHandler()


class InelnetOptionsFlowHandler(OptionsFlowWithReload):
    """Options flow to add or remove channels for an INELNET controller."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit channels for this controller."""
        if user_input is not None:
            try:
                channels = parse_channels(user_input[CONF_CHANNELS])
            except ValueError:
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                CONF_CHANNELS,
                                default=",".join(
                                    str(c)
                                    for c in self.config_entry.data.get(
                                        CONF_CHANNELS, [1]
                                    )
                                ),
                            ): str,
                        }
                    ),
                    errors={"base": "invalid_channels"},
                )
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_CHANNELS: channels},
            )
            return self.async_create_entry(title="", data={})

        current = self.config_entry.data.get(CONF_CHANNELS, [1])
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CHANNELS,
                        default=",".join(str(c) for c in current),
                    ): str,
                }
            ),
        )
