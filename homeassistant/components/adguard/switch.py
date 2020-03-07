"""Support for AdGuard Home switches."""
from datetime import timedelta
import logging

from adguardhome import AdGuardHomeConnectionError, AdGuardHomeError

from homeassistant.components.adguard import AdGuardHomeDeviceEntity
from homeassistant.components.adguard.const import (
    DATA_ADGUARD_CLIENT,
    DATA_ADGUARD_VERION,
    DOMAIN,
)
from homeassistant.components.switch import SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up AdGuard Home switch based on a config entry."""
    adguard = hass.data[DOMAIN][DATA_ADGUARD_CLIENT]

    try:
        version = await adguard.version()
    except AdGuardHomeConnectionError as exception:
        raise PlatformNotReady from exception

    hass.data[DOMAIN][DATA_ADGUARD_VERION] = version

    switches = [
        AdGuardHomeProtectionSwitch(adguard),
        AdGuardHomeFilteringSwitch(adguard),
        AdGuardHomeParentalSwitch(adguard),
        AdGuardHomeSafeBrowsingSwitch(adguard),
        AdGuardHomeSafeSearchSwitch(adguard),
        AdGuardHomeQueryLogSwitch(adguard),
    ]
    async_add_entities(switches, True)


class AdGuardHomeSwitch(AdGuardHomeDeviceEntity, SwitchDevice):
    """Defines a AdGuard Home switch."""

    def __init__(
        self, adguard, name: str, icon: str, key: str, enabled_default: bool = True
    ):
        """Initialize AdGuard Home switch."""
        self._state = False
        self._key = key
        super().__init__(adguard, name, icon, enabled_default)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join(
            [DOMAIN, self.adguard.host, str(self.adguard.port), "switch", self._key]
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._state

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the switch."""
        try:
            await self._adguard_turn_off()
        except AdGuardHomeError:
            _LOGGER.error("An error occurred while turning off AdGuard Home switch.")
            self._available = False

    async def _adguard_turn_off(self) -> None:
        """Turn off the switch."""
        raise NotImplementedError()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the switch."""
        try:
            await self._adguard_turn_on()
        except AdGuardHomeError:
            _LOGGER.error("An error occurred while turning on AdGuard Home switch.")
            self._available = False

    async def _adguard_turn_on(self) -> None:
        """Turn on the switch."""
        raise NotImplementedError()


class AdGuardHomeProtectionSwitch(AdGuardHomeSwitch):
    """Defines a AdGuard Home protection switch."""

    def __init__(self, adguard) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(
            adguard, "AdGuard Protection", "mdi:shield-check", "protection"
        )

    async def _adguard_turn_off(self) -> None:
        """Turn off the switch."""
        await self.adguard.disable_protection()

    async def _adguard_turn_on(self) -> None:
        """Turn on the switch."""
        await self.adguard.enable_protection()

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.protection_enabled()


class AdGuardHomeParentalSwitch(AdGuardHomeSwitch):
    """Defines a AdGuard Home parental control switch."""

    def __init__(self, adguard) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(
            adguard, "AdGuard Parental Control", "mdi:shield-check", "parental"
        )

    async def _adguard_turn_off(self) -> None:
        """Turn off the switch."""
        await self.adguard.parental.disable()

    async def _adguard_turn_on(self) -> None:
        """Turn on the switch."""
        await self.adguard.parental.enable()

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.parental.enabled()


class AdGuardHomeSafeSearchSwitch(AdGuardHomeSwitch):
    """Defines a AdGuard Home safe search switch."""

    def __init__(self, adguard) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(
            adguard, "AdGuard Safe Search", "mdi:shield-check", "safesearch"
        )

    async def _adguard_turn_off(self) -> None:
        """Turn off the switch."""
        await self.adguard.safesearch.disable()

    async def _adguard_turn_on(self) -> None:
        """Turn on the switch."""
        await self.adguard.safesearch.enable()

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.safesearch.enabled()


class AdGuardHomeSafeBrowsingSwitch(AdGuardHomeSwitch):
    """Defines a AdGuard Home safe search switch."""

    def __init__(self, adguard) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(
            adguard, "AdGuard Safe Browsing", "mdi:shield-check", "safebrowsing"
        )

    async def _adguard_turn_off(self) -> None:
        """Turn off the switch."""
        await self.adguard.safebrowsing.disable()

    async def _adguard_turn_on(self) -> None:
        """Turn on the switch."""
        await self.adguard.safebrowsing.enable()

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.safebrowsing.enabled()


class AdGuardHomeFilteringSwitch(AdGuardHomeSwitch):
    """Defines a AdGuard Home filtering switch."""

    def __init__(self, adguard) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(adguard, "AdGuard Filtering", "mdi:shield-check", "filtering")

    async def _adguard_turn_off(self) -> None:
        """Turn off the switch."""
        await self.adguard.filtering.disable()

    async def _adguard_turn_on(self) -> None:
        """Turn on the switch."""
        await self.adguard.filtering.enable()

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.filtering.enabled()


class AdGuardHomeQueryLogSwitch(AdGuardHomeSwitch):
    """Defines a AdGuard Home query log switch."""

    def __init__(self, adguard) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(
            adguard,
            "AdGuard Query Log",
            "mdi:shield-check",
            "querylog",
            enabled_default=False,
        )

    async def _adguard_turn_off(self) -> None:
        """Turn off the switch."""
        await self.adguard.querylog.disable()

    async def _adguard_turn_on(self) -> None:
        """Turn on the switch."""
        await self.adguard.querylog.enable()

    async def _adguard_update(self) -> None:
        """Update AdGuard Home entity."""
        self._state = await self.adguard.querylog.enabled()
