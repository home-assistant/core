"""Config flow for EvolvIOT."""

import asyncio
import base64
from contextlib import suppress
from io import BytesIO
from typing import Any

from PIL import Image
import qrcode
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EvolvIOTApi,
    EvolvIOTAuthError,
    EvolvIOTConnectionError,
    EvolvIOTDeviceAuthorizationDenied,
    EvolvIOTDeviceAuthorizationExpired,
    EvolvIOTDeviceAuthorizationPending,
    normalize_api_base_url,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_API_BASE_URL,
    CONF_REFRESH_TOKEN,
    CONF_VERIFY_SSL,
    DEFAULT_API_BASE_URL,
    DOMAIN,
    NAME,
)

QR_CANVAS_WIDTH = 520


def _connection_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    values = user_input or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_API_BASE_URL,
                default=values.get(CONF_API_BASE_URL, DEFAULT_API_BASE_URL),
            ): str,
            vol.Optional(
                CONF_VERIFY_SSL, default=values.get(CONF_VERIFY_SSL, True)
            ): bool,
        }
    )


def _retry_schema() -> vol.Schema:
    return vol.Schema({vol.Required("retry", default=True): bool})


def _pair_schema() -> vol.Schema:
    return vol.Schema({})


def _qr_code_data_uri(payload: str) -> str:
    """Return an embedded QR code image for the pairing payload."""
    if not payload:
        return ""

    qr_image = qrcode.make(payload, border=2).convert("RGBA")
    canvas_width = max(QR_CANVAS_WIDTH, qr_image.width)
    image = Image.new("RGBA", (canvas_width, qr_image.height), (255, 255, 255, 0))
    image.paste(qr_image, ((canvas_width - qr_image.width) // 2, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class EvolvIOTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an EvolvIOT config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_base_url = DEFAULT_API_BASE_URL
        self._verify_ssl = True
        self._pairing: dict[str, Any] = {}
        self._refresh_task: asyncio.Task[None] | None = None

    def _api(self) -> EvolvIOTApi:
        session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        return EvolvIOTApi(
            session,
            self._api_base_url,
            verify_ssl=self._verify_ssl,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Start app-based pairing immediately."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_base_url = normalize_api_base_url(
                user_input.get(CONF_API_BASE_URL, self._api_base_url)
            )
            self._verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, self._verify_ssl))

        try:
            await self._async_start_pairing()
        except EvolvIOTConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=_retry_schema(),
                errors=errors,
            )

        return await self.async_step_pair()

    async def async_step_pair(self, user_input: dict[str, Any] | None = None):
        """Show pairing details while polling for app approval."""
        errors: dict[str, str] = {}

        if not self._pairing:
            return await self.async_step_user()

        if user_input is not None:
            device_code = str(self._pairing["device_code"])
            try:
                token_data = await self._api().async_exchange_device_code(device_code)
                access_token = str(token_data.get("access_token") or "").strip()
                refresh_token = str(token_data.get("refresh_token") or "").strip()
                api = EvolvIOTApi(
                    async_get_clientsession(self.hass, verify_ssl=self._verify_ssl),
                    self._api_base_url,
                    access_token,
                    refresh_token=refresh_token,
                    verify_ssl=self._verify_ssl,
                )
                payload = await api.async_validate()
            except EvolvIOTDeviceAuthorizationPending:
                errors["base"] = "authorization_pending"
            except EvolvIOTDeviceAuthorizationExpired:
                return await self._async_refresh_pairing("authorization_expired")
            except EvolvIOTDeviceAuthorizationDenied:
                return await self._async_refresh_pairing("authorization_denied")
            except EvolvIOTAuthError:
                return await self._async_refresh_pairing("invalid_auth")
            except EvolvIOTConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                self._cancel_pairing_refresh()
                unique_id = str(payload.get("user_id") or self._api_base_url)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=NAME,
                    data={
                        CONF_API_BASE_URL: self._api_base_url,
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_VERIFY_SSL: self._verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="pair",
            data_schema=_pair_schema(),
            errors=errors,
            description_placeholders=self._pair_description_placeholders(),
        )

    async def _async_start_pairing(self) -> None:
        """Start a fresh pairing session."""
        self._cancel_pairing_refresh()
        self._pairing = await self._api().async_start_device_authorization()
        self._refresh_task = self.hass.async_create_task(
            self._async_refresh_pairing_on_expiry()
        )

    def _cancel_pairing_refresh(self) -> None:
        """Cancel the passive expiry refresh task."""
        current_task = asyncio.current_task()
        if (
            self._refresh_task is not None
            and self._refresh_task is not current_task
            and not self._refresh_task.done()
        ):
            self._refresh_task.cancel()
        if self._refresh_task is not current_task:
            self._refresh_task = None

    async def _async_refresh_pairing_on_expiry(self) -> None:
        """Refresh the QR/code when the current pairing session expires."""
        expires_in = max(1, int(self._pairing.get("expires_in") or 600))
        try:
            await asyncio.sleep(expires_in)
            await self._async_start_pairing()
            with suppress(UnknownFlow):
                await self.hass.config_entries.flow.async_configure(self.flow_id)
                self.async_notify_flow_changed()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            self._pairing = {}

    async def _async_refresh_pairing(self, error: str):
        """Replace the expired/invalid pairing session with a fresh one."""
        try:
            await self._async_start_pairing()
        except EvolvIOTConnectionError:
            self._pairing = {}
            return self.async_show_form(
                step_id="user",
                data_schema=_retry_schema(),
                errors={"base": "cannot_connect"},
            )
        except Exception:  # noqa: BLE001
            self._pairing = {}
            return self.async_show_form(
                step_id="user",
                data_schema=_retry_schema(),
                errors={"base": "unknown"},
            )
        else:
            errors = {"base": error}

        return self.async_show_form(
            step_id="pair",
            data_schema=_pair_schema(),
            errors=errors,
            description_placeholders=self._pair_description_placeholders(),
        )

    def _pair_description_placeholders(self) -> dict[str, str]:
        """Return placeholders shown in the pairing form step."""
        return {
            "qr_image_url": _qr_code_data_uri(
                str(self._pairing.get("qr_payload") or "")
            ),
            "user_code": str(self._pairing.get("user_code") or ""),
            "expires_in": str(self._pairing.get("expires_in") or ""),
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return EvolvIOTOptionsFlow(config_entry)


class EvolvIOTOptionsFlow(config_entries.OptionsFlow):
    """Handle EvolvIOT options updates."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Update stored connection details."""
        if user_input is not None:
            data = {
                **self.config_entry.data,
                CONF_API_BASE_URL: normalize_api_base_url(
                    user_input[CONF_API_BASE_URL]
                ),
                CONF_VERIFY_SSL: bool(user_input.get(CONF_VERIFY_SSL, True)),
            }
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_connection_schema(dict(self.config_entry.data)),
        )
