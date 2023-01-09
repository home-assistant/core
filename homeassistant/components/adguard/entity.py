"""AdGuard Home base entity."""
from __future__ import annotations

from adguardhome import AdGuardHome, AdGuardHomeError

from homeassistant.config_entries import SOURCE_HASSIO, ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DATA_ADGUARD_VERSION, DOMAIN, LOGGER


class AdGuardHomeEntity(Entity):
    """Defines a base AdGuard Home entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        adguard: AdGuardHome,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the AdGuard Home entity."""
        self._entry = entry
        self.adguard = adguard

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
        raise NotImplementedError()

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
            sw_version=self.hass.data[DOMAIN][self._entry.entry_id].get(
                DATA_ADGUARD_VERSION
            ),
            configuration_url=config_url,
        )
