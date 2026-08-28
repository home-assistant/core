"""OAuth2 login flow steps and token-expiry handling for the BLUETTI integration."""

from datetime import datetime, timedelta
import logging
import time
from typing import Any, cast, override

from aiohttp import ClientSession
from pybluetti import ProductClient, UserProduct

from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers import config_entry_oauth2_flow, issue_registry as ir
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_TOKEN_EXPIRED, NOTIFY_ID_TOKEN_EXPIRED

__LOGGER__ = logging.getLogger(__name__)

ISSUE_ID_OAUTH_EXPIRED = "oauth_expired"


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


class AsyncConfigEntryAuth:
    """Provide BLUETTI authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize BLUETTI auth."""
        self._websession = websession
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()
        return cast("str", self._oauth_session.token["access_token"])


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
        self._unsub_next_check: CALLBACK_TYPE | None = None
        unsub = hass.bus.async_listen(EVENT_TOKEN_EXPIRED, self.on_token_expired_event)
        entry.async_on_unload(unsub)
        # Single registration for whichever check is currently scheduled -
        # _schedule_next_check() replaces self._unsub_next_check on every
        # reschedule instead of registering a new on_unload callback each
        # time, which would otherwise grow unbounded over the entry's
        # lifetime.
        entry.async_on_unload(self._cancel_next_check)

    async def on_token_expired_event(self, event: Event[Any]) -> None:
        """Notify the user when the API reports the token has expired."""
        __LOGGER__.info("on_token_expired_event")
        self.send_expired_notification()

    def start_token_check(self) -> None:
        """Check the token now; each check reschedules the next one itself."""
        # first clear old notify
        persistent_notification.async_dismiss(
            self.hass, notification_id=NOTIFY_ID_TOKEN_EXPIRED
        )
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_ID_OAUTH_EXPIRED)
        if not self.is_token_valid():
            __LOGGER__.info("token have expired send notify")
            self.send_expired_notification()
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

    # check oauth2 token is ok
    def is_token_valid(self) -> bool:
        """Check token."""
        token = self.oAuth2Session.token
        if not token:
            return False

        if "expires_at" in token:
            expire_timestamp = cast("float", token["expires_at"]) - 30
            current_timestamp = time.time()
            return expire_timestamp > current_timestamp

        if "expires_in" in token and "created_at" in token:
            expire_timestamp = (
                cast("float", token["created_at"])
                + cast("float", token["expires_in"])
                - 30
            )
            current_timestamp = time.time()
            return expire_timestamp > current_timestamp

        return False

    # show token expire notify
    def send_expired_notification(self) -> None:
        """Show a persistent notification prompting the user to reauthenticate."""
        reauth_url = f"/config/integrations/integration/{DOMAIN}"
        notification_message = (
            "Your OAuth token has expired.\n"
            f"Please go to the **[integration settings]({reauth_url})** page and click [Reconfigure] to complete the login."
        )
        persistent_notification.async_create(
            self.hass,
            notification_message,
            title="OAuth Expired",
            notification_id=NOTIFY_ID_TOKEN_EXPIRED,
        )
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_ID_OAUTH_EXPIRED,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="oauth_expired",
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
                    if remain_timestamp < 0:
                        self.send_expired_notification()
                else:
                    last_refresh = current_timestamp

                    new_token = (
                        await self.oAuth2Session.implementation.async_refresh_token(
                            self.oAuth2Session.token
                        )
                    )
                    # async_update_entry() already fires the registered
                    # update listener, which reloads - no separate reload
                    # needed here.
                    self.hass.config_entries.async_update_entry(
                        self.entry,
                        data={
                            **self.entry.data,
                            "token": new_token,
                            "last_token_refresh": last_refresh,
                        },
                    )
                    __LOGGER__.info("refresh token ok")
            except OAuth2TokenRequestReauthError:
                # Non-recoverable: the refresh token itself is invalid or
                # revoked. Calling the implementation directly here (rather
                # than going through OAuth2Session, whose own
                # async_ensure_token_valid() would otherwise do this) means
                # nothing else starts reauth on our behalf - an entry with
                # no device coordinator has no other request that would.
                __LOGGER__.error("refresh token failed: refresh token is invalid")
                self.entry.async_start_reauth_if_available(self.hass)
                if remain_timestamp < 0:
                    self.send_expired_notification()
            except Exception as e:  # noqa: BLE001 - OAuth SDK call at a system boundary; logged, not fatal
                __LOGGER__.error("refresh token failed: %s", e)
                if remain_timestamp < 0:
                    self.send_expired_notification()

        self._schedule_next_check()
