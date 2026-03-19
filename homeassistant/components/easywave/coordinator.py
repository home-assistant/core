"""Coordinator for Easywave integration with automatic USB reconnect."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEVICE_SCAN_INTERVAL, DOMAIN
from .transceiver import RX11Transceiver

if TYPE_CHECKING:
    from . import EasywaveConfigEntry

_LOGGER = logging.getLogger(__name__)


class EasywaveCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Easywave integration."""

    config_entry: EasywaveConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        transceiver: RX11Transceiver,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEVICE_SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.transceiver = transceiver
        self.is_offline = not transceiver.is_connected

    async def async_setup(self) -> bool:
        """Setup coordinator and attempt initial data load.

        Returns True if setup successful (even in offline mode),
        False if initialization failed completely.
        """
        try:
            # Try initial connection
            connected = await self.transceiver.connect()
            self.is_offline = not connected

            if connected:
                # Register disconnect callback for immediate offline detection
                self.transceiver.set_disconnect_callback(
                    self._on_transceiver_disconnect
                )
            else:
                _LOGGER.warning(
                    "RX11 device not found, entering offline mode. "
                    "Entities will be unavailable until device connects"
                )
        except (OSError, TimeoutError) as err:
            _LOGGER.error("Setup failed: %s", err)
            return False
        else:
            # Always return True — offline mode is OK for setup
            return True

    def _on_transceiver_disconnect(self) -> None:
        """Called from transceiver when connection is lost.

        May be invoked from the event loop (health-check / RxModule
        disconnect handler), so use call_soon_threadsafe to guarantee
        thread safety regardless of the calling context.
        """
        self.hass.loop.call_soon_threadsafe(self._handle_disconnect)

    def _handle_disconnect(self) -> None:
        """Mark offline and push updated data to listeners immediately."""
        if self.is_offline:
            return
        _LOGGER.warning("Lost connection to RX11, entering offline mode")
        self.is_offline = True
        self.async_set_updated_data(
            {
                "is_connected": False,
                "device_path": None,
            }
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update device data periodically.

        This is called every DEVICE_SCAN_INTERVAL to:
        - Check connection status
        - Attempt reconnection if offline
        - Detect disconnections of previously connected devices
        """
        try:
            # If offline, attempt reconnect
            if self.is_offline:
                connected = await self.transceiver.reconnect()
                if connected:
                    self.is_offline = False
                    # Re-register disconnect callback for new connection
                    self.transceiver.set_disconnect_callback(
                        self._on_transceiver_disconnect
                    )
                    # Return new device state; coordinator will notify listeners
                    return {
                        "is_connected": self.transceiver.is_connected,
                        "device_path": self.transceiver.device_path,
                    }
                # Still offline, no need to log as error — offline mode is expected
                return {
                    "is_connected": False,
                    "device_path": None,
                }
            # Verify transceiver still reports connected
            # (disconnect callback handles immediate detection,
            # this is a safety net for edge cases)
            if not self.transceiver.is_connected:
                _LOGGER.warning("Connection lost, entering offline mode")
                self.is_offline = True
                return {
                    "is_connected": False,
                    "device_path": None,
                }
        except UpdateFailed:
            if not self.is_offline:
                self.is_offline = True
            raise
        except (OSError, TimeoutError) as err:
            _LOGGER.warning("Error updating coordinator data: %s", err)
            self.is_offline = True
            raise UpdateFailed(f"Update failed: {err}") from err
        else:
            return {
                "is_connected": self.transceiver.is_connected,
                "device_path": self.transceiver.device_path,
            }

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect transceiver."""
        try:
            await self.transceiver.disconnect()
            _LOGGER.debug("Coordinator shutdown complete")
        except (OSError, TimeoutError) as err:
            _LOGGER.error("Error during coordinator shutdown: %s", err)
        finally:
            await super().async_shutdown()
