"""Platform for Switch integration."""

from blastbot_cloud_api.models.control import Control

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Blastbot Cloud platform."""

    # Get API object from data
    api = hass.data[DOMAIN][entry.entry_id]

    # Add switches
    switches = await api.async_get_switches()
    async_add_entities(BlastbotSwitchEntity(switch) for switch in switches)


class BlastbotSwitchEntity(SwitchEntity):
    """Representation of a Blastbot Switch."""

    def __init__(self, control: Control) -> None:
        """Initialize the Switch."""
        self._control = control

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{DOMAIN}_c{self._control.id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._control.device["connected"]

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._control.name

    async def async_update(self) -> None:
        """Synchronize state with switch."""
        await self._control.async_update()

    @property
    def is_on(self) -> bool:
        """Return true if it is on."""
        return self._control.switch_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._control.async_control_switch(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._control.async_control_switch(False)

    @property
    def device_info(self):
        """Return device info."""
        model = "Blastbot Device"
        d_id = self._control.device["id"]
        d_type = self._control.device["type"]
        d_name = self._control.device["name"]
        if d_type == "blastbot-plug":
            model = "Blastbot Plug"
        if d_type == "blastbot-switch":
            model = "Blastbot Switch - 2 buttons"
        if d_type == "blastbot-switch-1":
            model = "Blastbot Switch - 1 button"
        if d_type == "blastbot-switch-3":
            model = "Blastbot Switch - 3 buttons"

        bridge_id = self._control.device["bridgeId"]

        info = {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f"d{d_id}")
            },
            "name": d_name,
            "manufacturer": "Blastbot",
            "model": model,
            "sw_version": self._control.device["version"],
        }

        if bridge_id is not None:
            info["via_device"] = (DOMAIN, f"d{bridge_id}")

        return info
