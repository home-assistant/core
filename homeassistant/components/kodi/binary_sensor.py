"""Binary sensor support for Kodi."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KodiConfigEntry, KodiRuntimeData
from .const import DOMAIN, async_signal_screensaver_update


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: KodiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kodi binary sensor entities."""
    data = config_entry.runtime_data
    if (uid := config_entry.unique_id) is None:
        uid = config_entry.entry_id

    await data.async_update_screensaver_state()

    async_add_entities(
        [
            KodiScreensaverBinarySensor(
                data,
                config_entry.data[CONF_NAME],
                uid,
                config_entry.entry_id,
            )
        ]
    )


class KodiScreensaverBinarySensor(BinarySensorEntity):
    """Representation of the Kodi screensaver state."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_translation_key = "screensaver"

    def __init__(
        self, runtime_data: KodiRuntimeData, name: str, uid: str, entry_id: str
    ) -> None:
        """Initialize the binary sensor."""
        self._runtime_data = runtime_data
        self._attr_unique_id = f"{uid}_screensaver"
        self._signal = async_signal_screensaver_update(entry_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            manufacturer="Kodi",
            name=name,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to screensaver state updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._signal, self._handle_screensaver_update
            )
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._runtime_data.connection.connected

    @property
    def is_on(self) -> bool | None:
        """Return the Kodi screensaver state."""
        return self._runtime_data.screensaver_active

    @callback
    def _handle_screensaver_update(self) -> None:
        """Handle shared screensaver state updates."""
        self.async_write_ha_state()
