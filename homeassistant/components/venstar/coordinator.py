"""Coordinator for the venstar component."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from requests import RequestException
from venstarcolortouch import VenstarColorTouch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator

from .const import _LOGGER, DOMAIN, VENSTAR_SLEEP


class VenstarDataUpdateCoordinator(update_coordinator.DataUpdateCoordinator[None]):
    """Class to manage fetching Venstar data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        venstar_connection: VenstarColorTouch,
    ) -> None:
        """Initialize global Venstar data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.client = venstar_connection
        self.runtimes: list[dict[str, int]] = []

    async def _async_update_data(self) -> None:
        """Update the state.

        The venstarcolortouch library catches all exceptions internally and
        returns False on failure instead of raising.  This means the
        OSError / RequestException handlers below will rarely fire, so we
        also check return values to detect silent failures and properly
        signal UpdateFailed to the coordinator.
        """
        try:
            info_success = await self.hass.async_add_executor_job(
                self.client.update_info
            )
        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during Venstar info update: {ex}"
            ) from ex

        if not info_success:
            raise update_coordinator.UpdateFailed(
                "Unable to update Venstar thermostat info"
            )

        # older venstars sometimes cannot handle rapid sequential connections
        await asyncio.sleep(VENSTAR_SLEEP)

        try:
            sensor_success = await self.hass.async_add_executor_job(
                self.client.update_sensors
            )
        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during Venstar sensor update: {ex}"
            ) from ex

        if not sensor_success:
            raise update_coordinator.UpdateFailed(
                "Unable to update Venstar sensor data"
            )

        # older venstars sometimes cannot handle rapid sequential connections
        await asyncio.sleep(VENSTAR_SLEEP)

        try:
            alerts_success = await self.hass.async_add_executor_job(
                self.client.update_alerts
            )
        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during Venstar alert update: {ex}"
            ) from ex

        if not alerts_success:
            raise update_coordinator.UpdateFailed("Unable to update Venstar alert data")

        # older venstars sometimes cannot handle rapid sequential connections
        await asyncio.sleep(VENSTAR_SLEEP)

        try:
            runtimes_result = await self.hass.async_add_executor_job(
                self.client.get_runtimes
            )
        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during Venstar runtime update: {ex}"
            ) from ex

        if not runtimes_result:
            raise update_coordinator.UpdateFailed(
                "Unable to update Venstar runtime data"
            )

        self.runtimes = runtimes_result
