"""Device token handling for the Famn integration."""

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from famn_sdk import ApiClient, ApiError, DeviceApi, DeviceTokenRefreshRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .const import CONF_REFRESH_TOKEN, DOMAIN

# Refresh ahead of the expiry reported by Famn, matching the reference
# device client, so a request never starts with a token that expires
# mid-flight. Access tokens live for 10 minutes.
TOKEN_EXPIRY_MARGIN = timedelta(seconds=90)

# Responses from the token endpoint that mean the device registration is
# no longer valid and the user has to pair again.
AUTH_FAILED_STATUS = (401, 403, 409, 410)


class FamnAuth:
    """Keep the access token of a paired Famn device valid.

    Famn hands out a short lived access token together with a refresh token
    that is single-use and rotates on every refresh. The rotated refresh
    token is persisted to the config entry immediately: reusing an old one
    trips server-side reuse detection which revokes all device tokens.
    """

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, client: ApiClient
    ) -> None:
        """Initialize the token handler."""
        self.hass = hass
        self.config_entry = config_entry
        self.client = client
        self._device_api = DeviceApi(client)
        self._access_token: str | None = None
        self._expires_at = dt_util.utcnow()
        self._lock = asyncio.Lock()

    @property
    def reauth_at(self) -> datetime:
        """Return when the current access token should be renewed."""
        return self._expires_at - TOKEN_EXPIRY_MARGIN

    @callback
    def invalidate(self) -> None:
        """Force a token rotation on the next request."""
        self._expires_at = dt_util.utcnow()

    async def async_get_access_token(self) -> str:
        """Return a currently valid access token."""
        await self.async_ensure_token_valid()
        if TYPE_CHECKING:
            assert self._access_token is not None
        return self._access_token

    async def async_ensure_token_valid(self) -> None:
        """Refresh the device tokens when the access token is about to expire.

        The rotation is shielded from cancellation. Famn's refresh token is
        single use and is spent the moment the request reaches the server, so
        an unload or a reload landing mid-flight would drop the replacement
        and leave the entry holding a token Famn has already consumed —
        presenting that on the next setup is what trips reuse detection and
        revokes the pairing.

        Raises `ApiError` for transient failures, so that callers can map them
        onto the error handling that fits their context.
        """
        if dt_util.utcnow() + TOKEN_EXPIRY_MARGIN < self._expires_at:
            return

        # The rotation runs as a config entry task, so that shielding it from
        # the caller's cancellation does not hide it from Home Assistant.
        await asyncio.shield(
            self.hass.async_create_task(
                self._async_rotate_if_needed(), "famn-token-rotation"
            )
        )

    async def _async_rotate_if_needed(self) -> None:
        """Rotate the device tokens and persist what Famn hands back.

        The lock is taken inside the shielded call, so a cancelled caller
        cannot release it while the rotation is still in flight.
        """
        async with self._lock:
            if dt_util.utcnow() + TOKEN_EXPIRY_MARGIN < self._expires_at:
                return

            try:
                tokens = await self._device_api.rotate_device_refresh_token_endpoint(
                    body=DeviceTokenRefreshRequest(
                        refresh_token=self.config_entry.data[CONF_REFRESH_TOKEN]
                    )
                )
            except ApiError as err:
                if err.status in AUTH_FAILED_STATUS:
                    raise ConfigEntryAuthFailed(
                        translation_domain=DOMAIN,
                        translation_key="token_rotation_unauthorized",
                    ) from err
                raise

            if (
                tokens.access_token is None
                or tokens.access_token_expires_at is None
                or tokens.refresh_token is None
            ):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="token_rotation_unauthorized",
                )

            # Persist the rotated refresh token before anything else can
            # fail; losing it invalidates the pairing.
            if tokens.refresh_token != self.config_entry.data[CONF_REFRESH_TOKEN]:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_REFRESH_TOKEN: tokens.refresh_token,
                    },
                )

            self.client.set_access_token(tokens.access_token)
            self._access_token = tokens.access_token
            self._expires_at = tokens.access_token_expires_at or dt_util.utcnow()
