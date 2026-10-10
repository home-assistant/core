"""DataUpdateCoordinator for Airlino."""

from typing import Any, override

from airlino_api import AirlinoApi, AirlinoApiConnectionError, AirlinoApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL


class AirlinoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate AirLino updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: AirlinoApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="AirLino",
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        # Device info (model, devicename, firmware) only changes on reboot or
        # a firmware update, so it is fetched once and refreshed whenever the
        # device comes back from being unreachable.
        self._device_info: dict[str, Any] | None = None
        self._refetch_device_info = False

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from AirLino devices."""
        previous = self.data if isinstance(self.data, dict) else None
        was_online = bool(previous and previous.get("online"))
        try:
            if self._device_info is None or self._refetch_device_info:
                self._device_info = await self.api.async_get_device_info()
                self._refetch_device_info = False
            player_status = await self.api.async_get_player_status()
            volume = await self.api.async_get_master_volume()
        except AirlinoApiConnectionError as err:
            # The device is unreachable (e.g. in standby). This is expected
            # and not an error: report it as data so the entity shows
            # unavailable without spamming the log. The last known device
            # info is kept so the device name is still shown for it.
            if was_online:
                LOGGER.info("AirLino is unreachable, assuming it is off")
            LOGGER.debug("AirLino is unreachable, assuming it is off: %s", err)
            self._refetch_device_info = True
            # Keep the last known device info so the device name is still
            # shown (e.g. in the multiroom selection) while unavailable.
            return {"online": False, "device": self._device_info}
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"err": str(err)},
            ) from err
        if not was_online:
            LOGGER.info("AirLino is available again")
        sender: dict[str, Any] | None = None
        receiver: dict[str, Any] | None = None
        try:
            sender = await self.api.async_get_sender_status()
            receiver = await self.api.async_get_receiver_state()
        except (AirlinoApiError, AirlinoApiConnectionError) as err:
            # Songcast is available since firmware/API v18, so an error here
            # is most likely a transient failure (e.g. the busy device times
            # out even though the core calls just succeeded). Do not fail the
            # whole update; the next cycle retries.
            LOGGER.debug("Songcast status not available on this device: %s", err)
        return {
            "online": True,
            "updated_at": dt_util.utcnow(),
            "device": self._device_info,
            "player": player_status,
            # Playback errors (e.g. unsupported https streams) are reported
            # by the device asynchronously in the player status.
            "error": player_status.get("error"),
            "volume": volume,
            "sender": sender,
            "receiver": receiver,
        }
