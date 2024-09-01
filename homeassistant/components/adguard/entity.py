"""AdGuard Home base entity."""

from __future__ import annotations

from adguardhome import AdGuardHomeError

from homeassistant.config_entries import SOURCE_HASSIO
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import AdGuardConfigEntry, AdGuardData
from .const import DOMAIN, LOGGER


class AdGuardHomeEntity(Entity):
    """Defines a base AdGuard Home entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        data: AdGuardData,
        entry: AdGuardConfigEntry,
    ) -> None:
        """Initialize the AdGuard Home entity."""
        self._entry = entry
        self.data = data
        self.adguard = data.client

    async def async_update(self) -> None:
        """Update AdGuard Home entity."""
        if not self.enabled:
            return

        try:
            await self._adguard_update()
            self._attr_available = True
        except AdGuardHomeError:
            if self._attr_available:
                LOGGER.debug(
                    "An error occurred while updating AdGuard Home sensor",
                    exc_info=True,
                )
            self._attr_available = False

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        raise NotImplementedError

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this AdGuard Home instance."""
        if self._entry.source == SOURCE_HASSIO:
            config_url = "homeassistant://hassio/ingress/a0d7b954_adguard"
        elif self.adguard.tls:
            config_url = f"https://{self.adguard.host}:{self.adguard.port}"
        else:
            config_url = f"http://{self.adguard.host}:{self.adguard.port}"

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (  # type: ignore[arg-type]
                    DOMAIN,
                    self.adguard.host,
                    self.adguard.port,
                    self.adguard.base_path,
                )
            },
            manufacturer="AdGuard Team",
            name="AdGuard Home",
            sw_version=self.data.version,
            configuration_url=config_url,
        )
