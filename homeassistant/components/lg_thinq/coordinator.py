"""DataUpdateCoordinator for the LG ThinQ device."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from thinqconnect import ThinQAPIException
from thinqconnect.integration import HABridge

from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import ThinqConfigEntry

from .const import DOMAIN, REVERSE_DEVICE_UNIT_TO_HA

_LOGGER = logging.getLogger(__name__)


class DeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """LG Device's Data Update Coordinator."""

    config_entry: ThinqConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ThinqConfigEntry, ha_bridge: HABridge
    ) -> None:
        """Initialize data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{ha_bridge.device.device_id}",
        )

        self.data = {}
        self.api = ha_bridge
        self.device_id = ha_bridge.device.device_id
        self.sub_id = ha_bridge.sub_id

        alias = ha_bridge.device.alias

        # The device name is usually set to 'alias'.
        # But, if the sub_id exists, it will be set to 'alias {sub_id}'.
        # e.g. alias='MyWashTower', sub_id='dryer' then 'MyWashTower dryer'.
        self.device_name = f"{alias} {self.sub_id}" if self.sub_id else alias

        # The unique id is usually set to 'device_id'.
        # But, if the sub_id exists, it will be set to 'device_id_{sub_id}'.
        # e.g. device_id='TQSXXXX', sub_id='dryer' then 'TQSXXXX_dryer'.
        self.unique_id = (
            f"{self.device_id}_{self.sub_id}" if self.sub_id else self.device_id
        )

        # Set your preferred temperature unit. This will allow us to retrieve
        # temperature values from the API in a converted value corresponding to
        # preferred unit.
        self._update_preferred_temperature_unit()

        # Add a callback to handle core config update.
        self.unit_system: str | None = None
        self.config_entry.async_on_unload(
            self.hass.bus.async_listen(
                event_type=EVENT_CORE_CONFIG_UPDATE,
                listener=self._handle_update_config,
                event_filter=self.async_config_update_filter,
            )
        )

    async def _handle_update_config(self, _: Event) -> None:
        """Handle update core config."""
        self._update_preferred_temperature_unit()

        await self.async_refresh()

    @callback
    def async_config_update_filter(self, event_data: Mapping[str, Any]) -> bool:
        """Filter out unwanted events."""
        if (unit_system := event_data.get("unit_system")) != self.unit_system:
            self.unit_system = unit_system
            return True

        return False

    def _update_preferred_temperature_unit(self) -> None:
        """Update preferred temperature unit."""
        self.api.set_preferred_temperature_unit(
            REVERSE_DEVICE_UNIT_TO_HA.get(self.hass.config.units.temperature_unit)
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Request to the server to update the status from full response data."""
        try:
            return await self.api.fetch_data()
        except ThinQAPIException as e:
            raise UpdateFailed(e) from e

    def refresh_status(self) -> None:
        """Refresh current status."""
        self.async_set_updated_data(self.data)

    def handle_update_status(self, status: dict[str, Any]) -> None:
        """Handle the status received from the mqtt connection."""
        data = self.api.update_status(status)
        if data is not None:
            self.async_set_updated_data(data)

    def handle_notification_message(self, message: str | None) -> None:
        """Handle the status received from the mqtt connection."""
        data = self.api.update_notification(message)
        if data is not None:
            self.async_set_updated_data(data)


async def async_setup_device_coordinator(
    hass: HomeAssistant, config_entry: ThinqConfigEntry, ha_bridge: HABridge
) -> DeviceDataUpdateCoordinator:
    """Create DeviceDataUpdateCoordinator and device_api per device."""
    coordinator = DeviceDataUpdateCoordinator(hass, config_entry, ha_bridge)
    await coordinator.async_refresh()

    _LOGGER.debug(
        "Setup device's coordinator: %s, model:%s",
        coordinator.device_name,
        coordinator.api.device.model_name,
    )
    return coordinator
