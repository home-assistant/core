"""The lookin integration config_flow."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiolookin import Device, LookInHttpProtocol, NoUsableService
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


class LookinFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for lookin."""

    def __init__(self) -> None:
        """Init the lookin flow."""
        self._host: str | None = None
        self._name: str | None = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Start a discovery flow from zeroconf."""
        uid: str = discovery_info.hostname.removesuffix(".local.")
        host: str = discovery_info.host
        await self.async_set_unique_id(uid.upper())
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            device: Device = await self._validate_device(host=host)
        except (aiohttp.ClientError, NoUsableService):
            return self.async_abort(reason="cannot_connect")
        except Exception:
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        self._name = device.name
        self._host = host
        self._set_confirm_only()
        self.context["title_placeholders"] = {
            "name": self._name or "LOOKin",
            "host": host,
        }
        return await self.async_step_discovery_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated discover flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                device = await self._validate_device(host=host)
            except (aiohttp.ClientError, NoUsableService):
                errors[CONF_HOST] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                device_id = device.id.upper()
                await self.async_set_unique_id(device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=device.name or host,
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def _validate_device(self, host: str) -> Device:
        """Validate we can connect to the device."""
        session = async_get_clientsession(self.hass)
        lookin_protocol = LookInHttpProtocol(f"http://{host}", session)
        return await lookin_protocol.get_info()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discover flow."""
        assert self._host is not None
        if user_input is None:
            return self.async_show_form(
                step_id="discovery_confirm",
                description_placeholders={
                    "name": self._name or "LOOKin",
                    "host": self._host,
                },
            )

        return self.async_create_entry(
            title=self._name or self._host,
            data={CONF_HOST: self._host},
        )
