"""DataUpdateCoordinator for the WattWächter integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aio_wattwaechter import (
    Wattwaechter,
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
    WattwaechterError,
    WattwaechterNoDataError,
)
from aio_wattwaechter.models import MeterData, OtaData, SystemInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FW_VERSION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LEGACY_MODEL_IDS,
    MODEL_NAMES,
)

_LOGGER = logging.getLogger(__name__)

type WattwaechterConfigEntry = ConfigEntry[WattwaechterCoordinator]


@dataclass
class WattwaechterData:
    """Data returned by a single WattWächter poll."""

    meter: MeterData
    system: SystemInfo | None
    ota: OtaData | None


class WattwaechterCoordinator(DataUpdateCoordinator[WattwaechterData]):
    """Coordinator for WattWächter data updates."""

    config_entry: WattwaechterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WattwaechterConfigEntry,
        client: Wattwaechter,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_id: str = config_entry.data[CONF_DEVICE_ID]
        self.host: str = config_entry.data[CONF_HOST]
        model: str | None = config_entry.data.get(CONF_MODEL)
        # Entries created before model IDs were reported store the mDNS model.
        self.model_id: str | None = (
            LEGACY_MODEL_IDS.get(model, model) if model else None
        )
        self.mac: str = config_entry.data[CONF_MAC]
        self.fw_version: str | None = config_entry.data.get(CONF_FW_VERSION)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{self.device_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @override
    async def _async_update_data(self) -> WattwaechterData:
        """Fetch data from the WattWächter device."""
        try:
            data = await self.client.meter_data()
        except WattwaechterNoDataError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_meter_data",
                translation_placeholders={"host": self.host},
            ) from err
        except WattwaechterAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except WattwaechterConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        if data is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_meter_data",
                translation_placeholders={"host": self.host},
            )

        # System info and OTA status are fetched best-effort: a failure here
        # must not take the meter sensors unavailable, so their entities just
        # report unknown until the next successful poll.
        system: SystemInfo | None
        try:
            system = await self.client.system_info()
        except WattwaechterError:
            system = None

        ota: OtaData | None
        try:
            ota = (await self.client.ota_check()).data
        except WattwaechterError:
            ota = None

        if system is not None:
            self._async_update_device_model(system)

        return WattwaechterData(meter=data, system=system, ota=ota)

    def device_model(self, system: SystemInfo | None) -> tuple[str | None, str | None]:
        """Return the model and model ID, preferring the system info.

        Gas/water devices report the product name for the configured medium
        (WattWächter Gas / WattWächter Wasser); older firmware reports none.
        """
        model_id = (system.model_id if system else None) or self.model_id
        model = (system.product_name if system else None) or MODEL_NAMES.get(
            model_id or ""
        )
        return model, model_id

    def _async_update_device_model(self, system: SystemInfo) -> None:
        """Update the registered model after a medium change or late system info."""
        model, model_id = self.device_model(system)
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, self.device_id), self.config_entry.entry_id
        )
        if device is not None and (device.model, device.model_id) != (
            model,
            model_id,
        ):
            device_registry.async_update_device(
                device.id, model=model, model_id=model_id
            )
