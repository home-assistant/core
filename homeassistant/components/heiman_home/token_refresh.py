"""Token Auto Refresh Manager for Heiman Home Integration.

Implements automatic OAuth2 token refresh with:
- 2-hour refresh interval (for 4-hour token expiry)
- Timer-based scheduling
- Retry logic with exponential backoff
- Token expiry monitoring with 5-minute safety margin
- Emergency refresh on API calls
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .heiman_cloud import HeimanCloudClient

from .heiman_error import HeimanError

_LOGGER = logging.getLogger(__name__)


class TokenRefreshManager:
    """Manages automatic token refresh for Heiman Cloud integration."""

    # Refresh interval: 2 hours (in seconds)
    # Token actual expires: 4 hours (7200s), with 70% ratio = 2.8 hours (5040s)
    # Set to 2 hours to ensure refresh before expiry
    REFRESH_INTERVAL_HOURS = 2
    REFRESH_INTERVAL_SECONDS = REFRESH_INTERVAL_HOURS * 3600

    # Retry configuration
    MAX_RETRY_ATTEMPTS = 5
    INITIAL_RETRY_DELAY = 30  # seconds
    MAX_RETRY_DELAY = 3600  # 1 hour
    RETRY_BACKOFF_FACTOR = 2

    # Token expiry margin (refresh before actual expiry)
    EXPIRY_MARGIN_SECONDS = 1800  # 30 minutes

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        cloud_client: HeimanCloudClient,
        on_token_refreshed: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize token refresh manager.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID
            cloud_client: Cloud client instance
            on_token_refreshed: Callback when token is refreshed successfully
        """
        self.hass = hass
        self.entry_id = entry_id
        self.cloud_client = cloud_client
        self.on_token_refreshed = on_token_refreshed

        self._refresh_timer: asyncio.TimerHandle | None = None
        self._time_interval_listener: Callable | None = None
        self._retry_count = 0
        self._last_refresh_time: float | None = None
        self._next_refresh_time: float | None = None
        self._is_running = False
        self._shutdown = False

    async def start_async(self) -> bool:
        """Start the auto-refresh timer.

        Returns:
            True if started successfully, False otherwise
        """
        if self._is_running:
            _LOGGER.debug("Token refresh already running")
            return True

        if self._shutdown:
            _LOGGER.warning("Cannot start: manager is shut down")
            return False

        # Check if we have a refresh token
        if not self.cloud_client.refresh_token:
            _LOGGER.warning("No refresh token available, cannot start auto-refresh")
            return False

        self._is_running = True
        self._shutdown = False

        # Calculate initial delay
        initial_delay = await self._calculate_initial_delay()

        _LOGGER.info(
            "Starting token auto-refresh (interval: %dh, initial delay: %.1fm)",
            self.REFRESH_INTERVAL_HOURS,
            initial_delay / 60,
        )

        # Schedule first refresh
        self._schedule_refresh(initial_delay)

        return True

    async def stop_async(self) -> None:
        """Stop the auto-refresh timer."""
        if not self._is_running:
            return

        _LOGGER.debug("Stopping token auto-refresh")

        self._is_running = False
        self._shutdown = True

        # Cancel scheduled refresh
        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None

        # Cancel time interval listener
        if self._time_interval_listener:
            self._time_interval_listener()
            self._time_interval_listener = None

        _LOGGER.info("Token auto-refresh stopped")

    async def refresh_now(self) -> bool:
        """Force an immediate token refresh.

        Returns:
            True if refresh was successful, False otherwise
        """
        if not self._is_running:
            _LOGGER.warning("Cannot refresh: manager is not running")
            return False

        _LOGGER.info("Forcing immediate token refresh...")
        return await self._do_refresh()

    def _schedule_refresh(self, delay_seconds: float) -> None:
        """Schedule a refresh after the specified delay.

        Args:
            delay_seconds: Delay in seconds
        """
        if not self._is_running or self._shutdown:
            return

        # Cancel existing timer
        if self._refresh_timer:
            self._refresh_timer.cancel()

        # Calculate next refresh time
        self._next_refresh_time = time.time() + delay_seconds

        _LOGGER.debug(
            "Scheduling token refresh in %.1fm (at %s)",
            delay_seconds / 60,
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._next_refresh_time)),
        )

        # Schedule using event loop timer
        self._refresh_timer = self.hass.loop.call_later(
            delay_seconds,
            lambda: self.hass.async_create_task(self._on_refresh_timer()),
        )

    async def _on_refresh_timer(self) -> None:
        """Called when refresh timer expires."""
        if not self._is_running or self._shutdown:
            return

        _LOGGER.debug("Token refresh timer triggered")

        success = await self._do_refresh()

        if success:
            # Reset retry count on success
            self._retry_count = 0

            # Schedule next regular refresh
            self._schedule_refresh(self.REFRESH_INTERVAL_SECONDS)
        else:
            # Retry with exponential backoff
            await self._handle_refresh_failure()

    async def _do_refresh(self) -> bool:
        """Perform the actual token refresh.

        Returns:
            True if successful, False otherwise
        """
        try:
            _LOGGER.debug("Refreshing access token...")
            await self.cloud_client.refresh_token_if_needed()
            self._last_refresh_time = time.time()
            if self.on_token_refreshed:
                token_data = {
                    "access_token": self.cloud_client.access_token,
                    "refresh_token": self.cloud_client.refresh_token,
                    "expires_ts": self.cloud_client.token_expires_ts,
                }
                self.on_token_refreshed(token_data)
            _LOGGER.info(
                "Token refreshed successfully (attempt %d)",
                self._retry_count + 1,
            )
        except HeimanError as err:
            _LOGGER.error("Failed to refresh token: %s", err)
            return False
        else:
            return True

    async def _handle_refresh_failure(self) -> None:
        """Handle refresh failure with retry logic."""
        self._retry_count += 1

        if self._retry_count >= self.MAX_RETRY_ATTEMPTS:
            _LOGGER.error(
                "Token refresh failed after %d attempts, giving up",
                self.MAX_RETRY_ATTEMPTS,
            )

            # Notify user about the failure
            if self.cloud_client.persistent_notify:
                self.cloud_client.persistent_notify(
                    "Token Refresh Failed",
                    f"Failed to refresh authentication token after {self.MAX_RETRY_ATTEMPTS} attempts. "
                    "Please re-authenticate in the integration settings.",
                    "alert",
                )

            # Stop auto-refresh
            await self.stop_async()
            return

        # Calculate retry delay with exponential backoff
        retry_delay = min(
            self.INITIAL_RETRY_DELAY
            * (self.RETRY_BACKOFF_FACTOR ** (self._retry_count - 1)),
            self.MAX_RETRY_DELAY,
        )

        _LOGGER.warning(
            "Token refresh failed (attempt %d/%d), retrying in %.1fm",
            self._retry_count,
            self.MAX_RETRY_ATTEMPTS,
            retry_delay / 60,
        )

        # Schedule retry
        self._schedule_refresh(retry_delay)

    async def _calculate_initial_delay(self) -> float:
        """Calculate initial delay before first refresh.

        Returns:
            Delay in seconds
        """
        # If token expires soon, refresh immediately
        if self.cloud_client.check_token_expiry():
            _LOGGER.info("Token already expired, will refresh immediately")
            return 0

        # Calculate time until token expires
        time_to_expiry = self.cloud_client.token_expires_ts - time.time()

        # If expires within margin, refresh soon
        if time_to_expiry <= self.EXPIRY_MARGIN_SECONDS:
            _LOGGER.info(
                "Token expires soon (%.1fm), refreshing in 5 minutes",
                time_to_expiry / 60,
            )
            return 300  # 5 minutes

        # Otherwise, use regular interval
        _LOGGER.info(
            "Token valid for %.1fh, will refresh in %.1fh",
            time_to_expiry / 3600,
            self.REFRESH_INTERVAL_HOURS / 3600,
        )
        return self.REFRESH_INTERVAL_SECONDS

    def get_status(self) -> dict[str, Any]:
        """Get current status of the refresh manager.

        Returns:
            Status dictionary
        """
        return {
            "is_running": self._is_running,
            "is_shutdown": self._shutdown,
            "retry_count": self._retry_count,
            "last_refresh_time": self._last_refresh_time,
            "next_refresh_time": self._next_refresh_time,
            "refresh_interval_hours": self.REFRESH_INTERVAL_HOURS,
        }

    async def cleanup_async(self) -> None:
        """Cleanup resources."""
        await self.stop_async()


class TokenRefreshCoordinator:
    """Coordinates token refresh across multiple config entries."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self._managers: dict[str, TokenRefreshManager] = {}

    def add_manager(self, entry_id: str, manager: TokenRefreshManager) -> None:
        """Add a refresh manager.

        Args:
            entry_id: Config entry ID
            manager: Token refresh manager
        """
        self._managers[entry_id] = manager
        _LOGGER.debug("Added token refresh manager for entry: %s", entry_id)

    def remove_manager(self, entry_id: str) -> None:
        """Remove a refresh manager.

        Args:
            entry_id: Config entry ID
        """
        if entry_id in self._managers:
            del self._managers[entry_id]
            _LOGGER.debug("Removed token refresh manager for entry: %s", entry_id)

    async def start_all_async(self) -> None:
        """Start all refresh managers."""
        for manager in self._managers.values():
            await manager.start_async()

    async def stop_all_async(self) -> None:
        """Stop all refresh managers."""
        for manager in self._managers.values():
            await manager.stop_async()

    async def refresh_all_async(self) -> dict[str, bool]:
        """Force refresh all tokens.

        Returns:
            Dict of entry_id -> success status
        """
        results = {}
        for entry_id, manager in self._managers.items():
            results[entry_id] = await manager.refresh_now()

        return results

    async def cleanup_async(self) -> None:
        """Cleanup all managers."""
        await self.stop_all_async()
        self._managers.clear()
