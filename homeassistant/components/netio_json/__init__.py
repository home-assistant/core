"""The NetIO JSON integration."""
from __future__ import annotations

import logging

from Netio.exceptions import NetioException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DATA_NETIO_CLIENT, DOMAIN
from .pdu import NetioPDU

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NetIO JSON from a config entry."""

    pdu = NetioPDU(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_NETIO_CLIENT: pdu}

    try:
        await pdu.async_initialize_pdu()
    except ConnectionError as ex:
        raise ConfigEntryNotReady(f"{pdu.host}: {ex}") from ex
    # except Exception as ex:
    #     template = "An exception of type {0} occurred. Arguments:\n{1!r}"
    #     message = template.format(type(ex).__name__, ex.args)
    #     _LOGGER.warning(message)
    #     raise ConfigEntryNotReady(f"ERROR for NetIO PDU {pdu.host}: ") from ex

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NetioEntity(Entity):
    """Defines a base NetIO PDU entity."""

    def __init__(
        self,
        pdu: NetioPDU,
        entry: ConfigEntry,
        name: str,
        icon: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize the NetIO PDU entity."""
        self._available = True
        self._enabled_default = enabled_default
        self._icon = icon
        self._name = name
        self._entry = entry
        self.pdu = pdu

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_update(self) -> None:
        """Update NetIO PDU entity."""
        if not self.enabled:
            return

        try:
            await self._pdu_update()
            self._available = True
        except NetioException:
            if self._available:
                _LOGGER.debug(
                    "An error occurred while updating NetIO PDU sensor",
                    exc_info=True,
                )
            self._available = False

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        raise NotImplementedError()


class NetioDeviceEntity(NetioEntity):
    """Defines a base NetIO PDU Device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this NetIO PDU instance."""

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.pdu.host, self.pdu.serial_number)},  # type: ignore[arg-type]
            default_name="NetIO PDU",
            manufacturer="NetIO",
            name=self.pdu.device_name,
            model=self.pdu.model,
            sw_version=self.pdu.sw_version,
            configuration_url=f"http://{self.pdu.host}/",
        )

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        raise NotImplementedError()
