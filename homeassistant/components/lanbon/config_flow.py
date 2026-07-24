"""Config flow for LANBON."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_TOKEN, DEFAULT_PORT, DOMAIN
from .coordinator import LanbonApi

_LOGGER = logging.getLogger(__name__)


async def _validate(hass: HomeAssistant, host: str, port: int, token: str) -> dict[str, Any]:
    """Validate connectivity and authentication to the Mesh root API."""
    api = LanbonApi(hass, host, port, token)
    return await api.async_get_info()


class LanbonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LANBON."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._token: str = ""
        self._mac: str | None = None
        self._sw_type: int | None = None
        self._type_name: str = "LANBON"

    def _set_type_name(self, name: Any | None) -> None:
        text = str(name).strip() if name is not None else ""
        self._type_name = text if text else "LANBON"
        self.context["title_placeholders"] = {"name": self._type_name}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
            token = user_input[CONF_TOKEN]
            try:
                info = await _validate(self.hass, host, port, token)
            except PermissionError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("LANBON connect failed")
                errors["base"] = "cannot_connect"
            else:
                if info.get("is_root") is False:
                    errors["base"] = "not_root"
                else:
                    mac = str(info.get("mac", host)).upper()
                    self._sw_type = info.get("sw_type")
                    self._set_type_name(info.get("type_name") or info.get("name"))
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: host, CONF_PORT: port}
                    )
                    return self.async_create_entry(
                        title=self._type_name,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_TOKEN: token,
                            "mac": mac,
                            "sw_type": self._sw_type,
                            "type_name": self._type_name,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host or ""): str,
                    vol.Required(CONF_PORT, default=self._port): int,
                    vol.Required(CONF_TOKEN, default=self._token): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        props = discovery_info.properties or {}
        norm = {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in props.items()
        }
        self._mac = (str(norm.get("mac") or "")).upper() or None
        self._token = str(norm.get("token") or "")
        try:
            self._sw_type = (
                int(norm.get("sw_type")) if norm.get("sw_type") is not None else None
            )
        except (TypeError, ValueError):
            self._sw_type = None
        self._set_type_name(norm.get("type_name") or discovery_info.name.split(".")[0])

        if self._mac:
            await self.async_set_unique_id(self._mac)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self._host, CONF_PORT: self._port}
            )
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered Mesh root."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input.get(CONF_TOKEN) or self._token
            try:
                info = await _validate(self.hass, self._host or "", self._port, token)
            except PermissionError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("LANBON connect failed")
                errors["base"] = "cannot_connect"
            else:
                if info.get("is_root") is False:
                    errors["base"] = "not_root"
                else:
                    mac = str(info.get("mac") or self._mac or "").upper()
                    if info.get("sw_type") is not None:
                        self._sw_type = info.get("sw_type")
                    self._set_type_name(
                        info.get("type_name") or info.get("name") or self._type_name
                    )
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: self._host, CONF_PORT: self._port}
                    )
                    return self.async_create_entry(
                        title=self._type_name,
                        data={
                            CONF_HOST: self._host,
                            CONF_PORT: self._port,
                            CONF_TOKEN: token,
                            "mac": mac,
                            "sw_type": self._sw_type,
                            "type_name": self._type_name,
                        },
                    )

        self._set_type_name(self._type_name)
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self._type_name,
                "host": self._host or "",
            },
            data_schema=vol.Schema(
                {vol.Required(CONF_TOKEN, default=self._token): str}
            ),
            errors=errors,
        )
