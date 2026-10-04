"""Config flow for the Famn integration."""

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, override
from urllib.parse import parse_qs, urlparse

from famn_sdk import (
    ApiClient,
    ApiError,
    DeviceApi,
    DevicePlatform,
    DeviceTokenResponse,
    PollDevicePairingRequest,
    StartDevicePairingRequest,
    StartDevicePairingResponse,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, __version__ as HA_VERSION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
)
from homeassistant.util import dt as dt_util

from .const import BASE_URL, CONF_REFRESH_TOKEN, DOMAIN, LOGGER

# Poll cadence of the reference device client: first poll shortly after
# start, then every 2.5 seconds. Transient errors back off exponentially.
FIRST_POLL_DELAY = 0.5
POLL_INTERVAL = 2.5
POLL_BACKOFF_MAX = 30.0

# The pairing is gone or expired; the flow has to be restarted.
PAIRING_GONE_STATUS = (401, 404, 410)


class FamnPairingExpired(Exception):
    """Raised when the pairing expired before the user approved it."""


class FamnPairingIncomplete(Exception):
    """Raised when an approved pairing response is missing required fields."""


def _pairing_link(pairing: StartDevicePairingResponse) -> tuple[str, str] | None:
    """Return the deep link that carries the pairing secret, and the secret.

    The secret is never returned as its own field: it is embedded as the `s`
    query parameter of a deep link, and Famn may put it on either the QR
    link or the verification link. The link is returned alongside it so that
    the QR encodes the one that can actually approve the pairing. The secret
    must be kept in memory only and never logged or persisted.
    """
    for url in (pairing.qr_url, pairing.verification_url):
        if url and (secret := parse_qs(urlparse(url).query).get("s")):
            return url, secret[0]
    return None


def _is_complete(tokens: DeviceTokenResponse) -> bool:
    """Return if an approved poll response contains all required fields."""
    return bool(
        tokens.access_token
        and tokens.access_token_expires_at
        and tokens.refresh_token
        and tokens.refresh_token_expires_at
        and tokens.device
        and tokens.device.id
        and tokens.device.relation_id
    )


class FamnConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Famn."""

    VERSION = 1

    pair_task: asyncio.Task[None] | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client: ApiClient | None = None
        self._pairing: StartDevicePairingResponse | None = None
        self._qr_url: str | None = None
        self._secret: str | None = None
        self._tokens: DeviceTokenResponse | None = None

    @override
    def async_remove(self) -> None:
        """Cancel pairing when the flow is removed."""
        super().async_remove()
        if self.pair_task is not None:
            self.pair_task.cancel()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the pairing QR and codes, and start polling in the background."""
        if self._client is None:
            self._client = ApiClient(
                BASE_URL, session=async_get_clientsession(self.hass)
            )

        if self._pairing is None:
            try:
                self._pairing = await DeviceApi(
                    self._client
                ).start_device_pairing_endpoint(
                    body=StartDevicePairingRequest(
                        app_version=HA_VERSION,
                        device_name="Home Assistant",
                        device_platform=DevicePlatform.LINUX,
                    )
                )
            except ApiError:
                LOGGER.exception("Could not start pairing with Famn")
                return self.async_abort(reason="cannot_connect")

            if (link := _pairing_link(self._pairing)) is None:
                LOGGER.error("Famn pairing response did not contain a secret")
                return self.async_abort(reason="cannot_connect")
            self._qr_url, self._secret = link

        # Poll in the background already while the QR is on screen, so the
        # flow finishes right away if the user approved before submitting.
        if self.pair_task is None:
            self.pair_task = self.hass.async_create_task(self._async_wait_for_pairing())

        if user_input is not None:
            return await self.async_step_wait()

        # The QR encodes the deep link exactly as Famn returned it, including
        # the pairing secret, mirroring the QR the Famn app scans on other
        # paired devices. It is the link the secret was found on, so scanning
        # it always approves the pairing.
        data_schema = vol.Schema(
            {
                vol.Optional("qr_code"): QrCodeSelector(
                    config=QrCodeSelectorConfig(
                        data=self._qr_url or "",
                        scale=5,
                        error_correction_level=QrErrorCorrectionLevel.QUARTILE,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="pair",
            data_schema=data_schema,
            description_placeholders=self._placeholders(),
        )

    async def async_step_wait(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the user to approve the pairing in the Famn app."""
        if TYPE_CHECKING:
            assert self.pair_task is not None

        if not self.pair_task.done():
            return self.async_show_progress(
                step_id="wait",
                progress_action="wait_for_pairing",
                description_placeholders=self._placeholders(),
                progress_task=self.pair_task,
            )

        if (exception := self.pair_task.exception()) is not None:
            self.pair_task = None
            self._pairing = None
            self._qr_url = None
            self._secret = None
            if isinstance(exception, FamnPairingExpired):
                return self.async_show_progress_done(next_step_id="timeout")
            LOGGER.error("Error while pairing with Famn: %s", exception)
            return self.async_show_progress_done(next_step_id="cannot_connect")

        return self.async_show_progress_done(next_step_id="finish")

    def _placeholders(self) -> dict[str, str]:
        """Return the description placeholders for the pairing steps."""
        if TYPE_CHECKING:
            assert self._pairing is not None
        return {
            "code": self._pairing.user_code or "",
            "pairing_id": str(self._pairing.pairing_id or ""),
            "url": self._pairing.verification_url or BASE_URL,
        }

    async def _async_wait_for_pairing(self) -> None:
        """Poll Famn until the user approves the pairing in the app.

        The approved poll response is one-shot: the server marks the pairing
        consumed immediately, so polling stops as soon as it arrives.
        """
        if TYPE_CHECKING:
            assert self._client is not None
            assert self._pairing is not None

        device_api = DeviceApi(self._client)
        expires_at = self._pairing.expires_at
        delay = FIRST_POLL_DELAY
        failures = 0

        while True:
            await asyncio.sleep(delay)

            if expires_at is not None and dt_util.utcnow() >= expires_at:
                raise FamnPairingExpired

            try:
                tokens = await device_api.poll_device_pairing_endpoint(
                    body=PollDevicePairingRequest(
                        pairing_id=self._pairing.pairing_id,
                        pairing_secret=self._secret,
                    )
                )
            except ApiError as err:
                if err.status in PAIRING_GONE_STATUS:
                    raise FamnPairingExpired from err
                # Transient failure: back off exponentially.
                failures += 1
                delay = min(float(2**failures), POLL_BACKOFF_MAX)
                continue

            failures = 0
            delay = POLL_INTERVAL

            if tokens.status == "approved":
                if not _is_complete(tokens):
                    # Approved, so nothing expired — Famn just did not send
                    # everything the pairing needs.
                    raise FamnPairingIncomplete
                self._tokens = tokens
                self._secret = None
                return

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Store the device tokens once pairing succeeded."""
        if TYPE_CHECKING:
            assert self._tokens is not None
            assert self._tokens.device is not None

        device = self._tokens.device
        data = {
            CONF_REFRESH_TOKEN: self._tokens.refresh_token,
            CONF_DEVICE_ID: str(device.id),
        }

        # The space the device was approved against is the stable identity
        # of the connection; re-pairing creates a new device id but keeps
        # the space.
        await self.async_set_unique_id(str(device.relation_id))

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=device.name or "Famn", data=data)

    async def async_step_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after the pairing code expired."""
        return self.async_abort(reason="pairing_timeout")

    async def async_step_cannot_connect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after a failure while polling for the pairing result."""
        return self.async_abort(reason="cannot_connect")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-pairing of a revoked or expired device."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm that the user wants to pair Home Assistant again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_pair()
