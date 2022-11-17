"""Support the UPB PIM."""
import upb_lib

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_COMMAND, CONF_FILE_PATH, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    ATTR_ADDRESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_RATE,
    DOMAIN,
    EVENT_UPB_SCENE_CHANGED,
)

PLATFORMS = [Platform.LIGHT, Platform.SCENE]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a new config_entry for UPB PIM."""

    url = config_entry.data[CONF_HOST]
    file = config_entry.data[CONF_FILE_PATH]

    upb = upb_lib.UpbPim({"url": url, "UPStartExportFile": file})
    upb.connect()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {"upb": upb}

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    def _element_changed(element, changeset):
        if (change := changeset.get("last_change")) is None:
            return
        if change.get("command") is None:
            return

        hass.bus.async_fire(
            EVENT_UPB_SCENE_CHANGED,
            {
                ATTR_COMMAND: change["command"],
                ATTR_ADDRESS: element.addr.index,
                ATTR_BRIGHTNESS_PCT: change.get("level", -1),
                ATTR_RATE: change.get("rate", -1),
            },
        )

    for link in upb.links:
        element = upb.links[link]
        element.add_callback(_element_changed)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the config_entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        upb = hass.data[DOMAIN][config_entry.entry_id]["upb"]
        upb.disconnect()
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok


class UpbEntity(Entity):
    """Base class for all UPB entities."""

    _attr_should_poll = False

    def __init__(self, element, unique_id, upb):
        """Initialize the base of all UPB devices."""
        self._upb = upb
        self._element = element
        element_type = "link" if element.addr.is_link else "device"
        self._unique_id = f"{unique_id}_{element_type}_{element.addr}"

    @property
    def unique_id(self):
        """Return unique id of the element."""
        return self._unique_id

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        return self._element.as_dict()

    @property
    def available(self):
        """Is the entity available to be updated."""
        return self._upb.is_connected()

    def _element_changed(self, element, changeset):
        pass

    @callback
    def _element_callback(self, element, changeset):
        """Handle callback from an UPB element that has changed."""
        self._element_changed(element, changeset)
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register callback for UPB changes and update entity state."""
        self._element.add_callback(self._element_callback)
        self._element_callback(self._element, {})


class UpbAttachedEntity(UpbEntity):
    """Base class for UPB attached entities."""

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._element.index)},
            manufacturer=self._element.manufacturer,
            model=self._element.product,
            name=self._element.name,
            sw_version=self._element.version,
        )
