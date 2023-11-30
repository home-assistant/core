"""Class to manage satellite devices."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


@dataclass
class SatelliteDevice:
    """Class to store device."""

    satellite_id: str
    device_id: str
    is_active: bool = False
    is_enabled: bool = True
    update_listeners: list[Callable[[SatelliteDevice], None]] = field(
        default_factory=list
    )

    @callback
    def set_is_active(self, active: bool) -> None:
        """Set active state."""
        self.is_active = active
        for listener in self.update_listeners:
            listener(self)

    @callback
    def set_is_enabled(self, enabled: bool) -> None:
        """Set enabled state."""
        self.is_enabled = enabled
        for listener in self.update_listeners:
            listener(self)

    @callback
    def async_pipeline_changed(self) -> None:
        """Inform listeners that pipeline selection has changed."""
        for listener in self.update_listeners:
            listener(self)

    @callback
    def async_listen_update(
        self, listener: Callable[[SatelliteDevice], None]
    ) -> Callable[[], None]:
        """Listen for updates."""
        self.update_listeners.append(listener)
        return lambda: self.update_listeners.remove(listener)


class SatelliteDevices:
    """Class to store devices."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize satellite devices."""
        self.hass = hass
        self.config_entry = config_entry
        self._new_device_listeners: list[Callable[[SatelliteDevice], None]] = []
        self.devices: dict[str, SatelliteDevice] = {}

    @callback
    def async_setup(self) -> None:
        """Set up devices."""
        for device in dr.async_entries_for_config_entry(
            dr.async_get(self.hass), self.config_entry.entry_id
        ):
            satellite_id = next(
                (item[1] for item in device.identifiers if item[0] == DOMAIN), None
            )
            if satellite_id is None:
                continue
            self.devices[satellite_id] = SatelliteDevice(
                satellite_id=satellite_id,
                device_id=device.id,
            )

        @callback
        def async_device_removed(ev: Event) -> None:
            """Handle device removed."""
            removed_id = ev.data["device_id"]
            self.devices.pop(removed_id, None)

        self.config_entry.async_on_unload(
            self.hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                async_device_removed,
                callback(lambda ev: ev.data.get("action") == "remove"),
            )
        )

    @callback
    def async_add_new_device_listener(
        self, listener: Callable[[SatelliteDevice], None]
    ) -> None:
        """Add a new device listener."""
        self._new_device_listeners.append(listener)

    @callback
    def async_get_or_create(self, suggested_area: str | None = None) -> SatelliteDevice:
        """Get or create a device."""
        dev_reg = dr.async_get(self.hass)
        satellite_id = self.config_entry.entry_id
        satellite_device = self.devices.get(satellite_id)

        if satellite_device is not None:
            return satellite_device

        device = dev_reg.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, satellite_id)},
            name=satellite_id,
            suggested_area=suggested_area,
        )

        satellite_device = self.devices[satellite_id] = SatelliteDevice(
            satellite_id=satellite_id,
            device_id=device.id,
        )
        for listener in self._new_device_listeners:
            listener(satellite_device)

        return satellite_device

    def __iter__(self) -> Iterator[SatelliteDevice]:
        """Iterate over devices."""
        return iter(self.devices.values())
