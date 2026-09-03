"""OAuth2 login flow steps and token-expiry handling for the BLUETTI integration."""

from datetime import datetime, timedelta
import logging
import time
from typing import Any, override

from pybluetti import ProductClient, StompClient, UserProduct

from homeassistant import config_entries
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import DOMAIN, token_expired_signal

__LOGGER__ = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """BLUETTI OAUTH2 handler."""

    DOMAIN = DOMAIN
    reauth_supported = True

    _oauth_data: dict[str, Any]
    _product_client: ProductClient
    _products: list[UserProduct]
    entry: config_entries.ConfigEntry

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select which BLUETTI devices to add.

        Overridden by BluettiConfigFlow, which is the only concrete
        subclass of this handler; kept here (rather than left undeclared)
        so the call in async_oauth_create_entry below type-checks.
        """
        raise NotImplementedError

    @override
    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle OAuth2 callback and create config entry."""
        self._oauth_data = data
        return await self.async_step_select_devices()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Reauth configure."""
        found_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if found_entry is None:
            return self.async_abort(reason="reconfigure_failed")
        self.entry = found_entry

        return await self.async_step_user()


class AuthTokenRefresh:
    """Handler Token expired and refresh token."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Wire up the expiry listener and periodic check for this entry's token."""
        self.hass = hass
        self.entry = entry
        self.oAuth2Session = oauth_session
        # Set via bind_clients() once product_client/stomp_client exist -
        # both are constructed after this object (see __init__.py), since
        # this object must be listening for an auth-expired signal before
        # either client's first request, not after.
        self._product_client: ProductClient | None = None
        self._stomp_client: StompClient | None = None
        self._unsub_next_check: CALLBACK_TYPE | None = None
        unsub = async_dispatcher_connect(
            hass, token_expired_signal(entry.entry_id), self.on_token_expired_event
        )
        entry.async_on_unload(unsub)
        # Single registration for whichever check is currently scheduled -
        # _schedule_next_check() replaces self._unsub_next_check on every
        # reschedule instead of registering a new on_unload callback each
        # time, which would otherwise grow unbounded over the entry's
        # lifetime.
        entry.async_on_unload(self._cancel_next_check)

    def bind_clients(
        self, product_client: ProductClient, stomp_client: StompClient
    ) -> None:
        """Attach the clients a successful proactive refresh should update.

        Called once both exist (see __init__.py's setup order) - a refresh
        landing before this runs simply has nothing to update yet, the same
        as it would on any setup that hasn't reached this point.
        """
        self._product_client = product_client
        self._stomp_client = stomp_client

    def on_token_expired_event(self) -> None:
        """Start reauth when the API reports the token has expired."""
        __LOGGER__.info("on_token_expired_event")
        self.entry.async_start_reauth_if_available(self.hass)

    def start_token_check(self) -> None:
        """Check the token now; each check reschedules the next one itself."""
        # Entry-scoped so it's canceled on unload, rather than a bare
        # hass-level task outliving the entry.
        self.entry.async_create_background_task(
            self.hass,
            self.async_check_token_expiry(),
            name="bluetti_initial_token_expiry_check",
        )

    def _cancel_next_check(self) -> None:
        """Cancel whichever future check is currently scheduled, if any."""
        if self._unsub_next_check is not None:
            self._unsub_next_check()
            self._unsub_next_check = None

    def _schedule_next_check(self) -> None:
        """Schedule the next expiry check, sooner the closer the token is to expiring.

        A fixed daily interval would reach a short-lived token (one that
        expires in under a day) too late - it would already be expired and
        handed to the fixed-token REST/WebSocket clients by the time the
        next check ran. Halving the remaining time each check (capped
        between 5 minutes and 1 day) always checks again well before the
        token could expire, without polling needlessly often for the
        common case of a long-lived token.
        """
        self._cancel_next_check()
        expire_timestamp = self.oAuth2Session.token.get("expires_at")
        if expire_timestamp is None:
            return
        remaining = timedelta(seconds=expire_timestamp - time.time())
        delay = min(timedelta(days=1), max(timedelta(minutes=5), remaining / 2))
        self._unsub_next_check = async_track_point_in_time(
            self.hass, self.async_check_token_expiry, dt_util.utcnow() + delay
        )

    # check token is in 7 day if in 7day refresh token
    async def async_check_token_expiry(self, now: datetime | None = None) -> None:
        """Check whether the token needs a refresh, and refresh it if so.

        Registered directly as the callback for async_track_point_in_time,
        which always calls it with the point in time it fired at - `now`
        must be accepted even though this method doesn't use it, or every
        fire raises TypeError and silently breaks the proactive check.
        Also called manually with no argument (start_token_check, on the
        first check), which is why it stays optional. Reschedules itself
        at the end - see _schedule_next_check.
        """
        __LOGGER__.info("check token is expired")
        expire_timestamp = self.oAuth2Session.token.get("expires_at")
        if expire_timestamp is None:
            __LOGGER__.warning("No expires_at in token, skipping expiry check")
            return
        current_timestamp = time.time()
        remain_timestamp = expire_timestamp - current_timestamp

        # Also tries an already-expired token, not just an expiring one - a
        # refresh token normally covers this fine.
        if remain_timestamp < 3600 * 24 * 7:
            try:
                __LOGGER__.info("start refresh token")
                last_refresh = self.entry.data.get("last_token_refresh", 0.0)
                # 1 hour only one time ,when server is 500 do not always refresh token
                if current_timestamp - last_refresh < 3600:
                    __LOGGER__.info(
                        "last refresh token in 1 hour,this do not refresh return"
                    )
                else:
                    last_refresh = current_timestamp

                    new_token = (
                        await self.oAuth2Session.implementation.async_refresh_token(
                            self.oAuth2Session.token
                        )
                    )
                    # Persisted so a restart doesn't start from the old
                    # token, but this integration registers no update
                    # listener - a proactive background refresh updating the
                    # stored token must not reload the entry (that would
                    # tear down every device's coordinator and the
                    # websocket just to swap in a token update_access_token
                    # below already hands the running clients directly).
                    self.hass.config_entries.async_update_entry(
                        self.entry,
                        data={
                            **self.entry.data,
                            "token": new_token,
                            "last_token_refresh": last_refresh,
                        },
                    )
                    new_access_token = new_token["access_token"]
                    if self._product_client is not None:
                        self._product_client.update_access_token(new_access_token)
                    if self._stomp_client is not None:
                        self._stomp_client.update_access_token(new_access_token)
                    __LOGGER__.info("refresh token ok")
            except OAuth2TokenRequestReauthError:
                # Non-recoverable: the refresh token itself is invalid or
                # revoked. Calling the implementation directly here (rather
                # than going through OAuth2Session, whose own
                # async_ensure_token_valid() would otherwise do this) means
                # nothing else starts reauth on our behalf - an entry with
                # no device coordinator has no other request that would.
                # async_start_reauth_if_available() alone is the canonical
                # way to surface this - it marks the entry as needing
                # attention in the UI, which a separate persistent
                # notification and repair issue for the same condition would
                # only duplicate.
                __LOGGER__.error("refresh token failed: refresh token is invalid")
                self.entry.async_start_reauth_if_available(self.hass)
            except Exception as e:  # noqa: BLE001 - OAuth SDK call at a system boundary; logged, not fatal
                __LOGGER__.error("refresh token failed: %s", e)

        self._schedule_next_check()
