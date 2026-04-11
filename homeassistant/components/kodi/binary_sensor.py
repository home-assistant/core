"""Binary sensor support for Kodi."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KodiConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: KodiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kodi binary sensor entities."""
    data = config_entry.runtime_data
    if (uid := config_entry.unique_id) is None:
        uid = config_entry.entry_id

    data.screensaver.set_hass(hass)
    await data.screensaver.async_update()

    async_add_entities(
        [
            KodiScreensaverBinarySensor(
                data.screensaver,
                config_entry.data[CONF_NAME],
                uid,
            )
        ]
    )


class KodiScreensaverBinarySensor(BinarySensorEntity):
    """Representation of the Kodi screensaver state."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_translation_key = "screensaver"

    def __init__(self, screensaver, name: str, uid: str) -> None:
        """Initialize the binary sensor."""
        self._screensaver = screensaver
        self._attr_unique_id = f"{uid}_screensaver"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            manufacturer="Kodi",
            name=name,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to screensaver state updates."""
        self._screensaver.set_hass(self.hass)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._screensaver.signal, self._handle_screensaver_update
            )
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._screensaver.available

    @property
    def is_on(self) -> bool | None:
        """Return the Kodi screensaver state."""
        return self._screensaver.is_on

    @callback
    def _handle_screensaver_update(self) -> None:
        """Handle shared screensaver state updates."""
        self.async_write_ha_state()
