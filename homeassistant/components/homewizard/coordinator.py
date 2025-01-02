"""Update coordinator for HomeWizard."""

from __future__ import annotations

import logging

from homewizard_energy import HomeWizardEnergyV1
from homewizard_energy.errors import DisabledError, RequestError, UnsupportedError
from homewizard_energy.v1.const import SUPPORTS_IDENTIFY, SUPPORTS_STATE
from homewizard_energy.v1.models import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, DeviceResponseEntry

_LOGGER = logging.getLogger(__name__)


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Gather data for the energy device."""

    api: HomeWizardEnergyV1
    api_disabled: bool = False

    _unsupported_error: bool = False

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = HomeWizardEnergyV1(
            self.config_entry.data[CONF_IP_ADDRESS],
            clientsession=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> DeviceResponseEntry:
        """Fetch all device and sensor data from api."""
        try:
            data = DeviceResponseEntry(
                device=await self.api.device(),
                data=await self.api.data(),
            )

            try:
                if self.supports_state(data.device):
                    data.state = await self.api.state()

                data.system = await self.api.system()

            except UnsupportedError as ex:
                # Old firmware, ignore
                if not self._unsupported_error:
                    self._unsupported_error = True
                    _LOGGER.warning(
                        "%s is running an outdated firmware version (%s). Contact HomeWizard support to update your device",
                        self.config_entry.title,
                        ex,
                    )

        except RequestError as ex:
            raise UpdateFailed(
                ex, translation_domain=DOMAIN, translation_key="communication_error"
            ) from ex

        except DisabledError as ex:
            if not self.api_disabled:
                self.api_disabled = True

                # Do not reload when performing first refresh
                if self.data is not None:
                    # Reload config entry to let init flow handle retrying and trigger repair flow
                    self.hass.config_entries.async_schedule_reload(
                        self.config_entry.entry_id
                    )

            raise UpdateFailed(
                ex, translation_domain=DOMAIN, translation_key="api_disabled"
            ) from ex

        self.api_disabled = False

        self.data = data
        return data

    def supports_state(self, device: Device | None = None) -> bool:
        """Return True if the device supports state."""

        if device is None:
            device = self.data.device

        return device.product_type in SUPPORTS_STATE

    def supports_identify(self, device: Device | None = None) -> bool:
        """Return True if the device supports identify."""
        if device is None:
            device = self.data.device

        return device.product_type in SUPPORTS_IDENTIFY
