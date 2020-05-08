"""Support the UPB PIM."""
import asyncio

import upb_lib

from homeassistant.const import CONF_FILE_PATH, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

UPB_PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the UPB platform."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up a new config_entry for UPB PIM."""

    url = config_entry.data[CONF_HOST]
    file = config_entry.data[CONF_FILE_PATH]

    upb = upb_lib.UpbPim({"url": url, "UPStartExportFile": file})
    upb.connect()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {"upb": upb}

    for component in UPB_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload the config_entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in UPB_PLATFORMS
            ]
        )
    )

    if unload_ok:
        upb = hass.data[DOMAIN][config_entry.entry_id]["upb"]
        upb.disconnect()
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class UpbEntity(Entity):
    """Base class for all UPB entities."""

    def __init__(self, element, unique_id, upb):
        """Initialize the base of all UPB devices."""
        self._upb = upb
        self._element = element
        element_type = "link" if element.addr.is_link else "device"
        self._unique_id = f"{unique_id}_{element_type}_{element.addr}"

    @property
    def name(self):
        """Name of the element."""
        return self._element.name

    @property
    def unique_id(self):
        """Return unique id of the element."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """Don't poll this device."""
        return False

    @property
    def device_state_attributes(self):
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
    def device_info(self):
        """Device info for the entity."""
        return {
            "name": self._element.name,
            "identifiers": {(DOMAIN, self._element.index)},
            "sw_version": self._element.version,
            "manufacturer": self._element.manufacturer,
            "model": self._element.product,
        }
