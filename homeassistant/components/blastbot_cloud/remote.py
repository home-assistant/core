"""Platform for IR/RF remote integration."""

from blastbot_cloud_api.models.control import Control

from homeassistant.components.remote import RemoteEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Blastbot Cloud platform."""

    # Get API object from data
    api = hass.data[DOMAIN][entry.entry_id]

    # Add switches
    irs = await api.async_get_irs()
    entries = []
    for control in irs:
        for button in control.buttons:
            entries.append(BlastbotRemoteEntity(control, button))

    async_add_entities(entries)


class BlastbotRemoteEntity(RemoteEntity):
    """Representation of a Blastbot Remote."""

    def __init__(self, control: Control, button) -> None:
        """Initialize the Remote."""
        self._control = control
        self._button = button
        self._button_id = button["id"]

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{DOMAIN}_c{self._control.id}b{self._button_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._control.device["connected"]

    @property
    def name(self) -> str:
        """Return the name of the remote."""
        return self._button["name"]

    @property
    def should_poll(self) -> bool:
        """Return that it should not poll remotes."""
        return False

    async def async_update(self) -> None:
        """Synchronize state with remote."""
        await self._control.async_update()

    @property
    def is_on(self) -> bool:
        """Remote buttons are always off."""
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Execute button action on state change."""
        await self._control.async_control_button(self._button_id)

    async def async_turn_off(self, **kwargs) -> None:
        """Execute button action on state change."""
        await self._control.async_control_button(self._button_id)

    @property
    def device_info(self):
        """Return device info."""
        model = "Blastbot Device"
        d_id = self._control.device["id"]
        d_type = self._control.device["type"]
        d_name = self._control.device["name"]
        if d_type == "blastbot-ir":
            model = "Blastbot Smart Control"
        if d_type == "blastbot-hub":
            model = "Blastbot Hub"

        bridge_id = self._control.device["bridgeId"]

        info = {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f"d{d_id}c{self._control.id}")
            },
            "name": f"{d_name} - {self._control.name}",
            "manufacturer": "Blastbot",
            "model": model,
            "sw_version": self._control.device["version"],
        }

        if bridge_id is not None:
            info["via_device"] = (DOMAIN, f"d{bridge_id}")

        return info
