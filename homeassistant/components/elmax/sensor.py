"""Elmax sensor platform."""
from typing import Any, Mapping, Optional

from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus

from homeassistant.components.binary_sensor import DEVICE_CLASS_DOOR, BinarySensorEntity
from homeassistant.components.elmax import ElmaxCoordinator, ElmaxEntity
from homeassistant.components.elmax.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType


class ElmaxSensor(ElmaxEntity, BinarySensorEntity):
    """Elmax Sensor entity implementation."""

    def __init__(
        self,
        panel: PanelEntry,
        elmax_device: DeviceEndpoint,
        panel_version: str,
        coordinator: ElmaxCoordinator,
    ):
        """Construct the object."""
        super().__init__(panel, elmax_device, panel_version, coordinator)

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the binary sensor is on."""
        return self._device.opened

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_DOOR

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        """Return extra attributes."""
        attrs = super().extra_state_attributes
        if attrs is None:
            attrs = {}
        else:
            attrs = dict(attrs)
        attrs.update(
            {
                "excluded": self._device.excluded,
            }
        )
        return attrs

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return "hass:door-open" if self.is_on else "hass:door"


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up the Elmax sensor platform."""
    coordinator: ElmaxCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    def _discover_new_devices():
        panel_status = coordinator.panel_status  # type: PanelStatus
        # In case the panel is offline, its status will be None. In that case, simply do nothing
        if panel_status is None:
            return

        # Otherwise, add all the entities we found
        entities = []
        for zone in panel_status.zones:
            e = ElmaxSensor(
                panel=coordinator.panel_entry,
                elmax_device=zone,
                panel_version=panel_status.release,
                coordinator=coordinator,
            )
            if e.unique_id not in known_devices:
                entities.append(e)

        async_add_entities(entities, True)
        known_devices.update([e.unique_id for e in entities])

    # Register a listener for the discovery of new devices
    coordinator.async_add_listener(_discover_new_devices)

    # Immediately run a discovery, so we don't need to wait for the next update
    _discover_new_devices()


# TODO unload
