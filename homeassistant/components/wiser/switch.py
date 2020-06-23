"""
Switch  Platform Device for Wiser Rooms.

https://github.com/asantaga/wiserHomeAssistantPlatform
Angelosantagata@gmail.com
"""
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import _LOGGER, DATA, DOMAIN, MANUFACTURER, WISER_SERVICES, WISER_SWITCHES

try:
    from homeassistant.components.switch import SwitchEntity
except ImportError:
    from homeassistant.components.switch import SwitchDevice as SwitchEntity

ATTR_PLUG_MODE = "plug_mode"
ATTR_HOTWATER_MODE = "hotwater_mode"

SET_PLUG_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_PLUG_MODE, default="Auto"): vol.Coerce(str),
    }
)

SET_HOTWATER_MODE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_HOTWATER_MODE, default="auto"): vol.Coerce(str)}
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Wiser System Switch entities."""
    data = hass.data[DOMAIN][config_entry.entry_id][DATA]  # Get Handler

    # Add System Switches
    wiser_switches = []
    for switch in WISER_SWITCHES:
        wiser_switches.append(
            WiserSwitch(data, switch["name"], switch["key"], switch["icon"])
        )

    async_add_entities(wiser_switches)

    # Add SmartPlugs (if any)
    if data.wiserhub.getSmartPlugs() is not None:
        wiser_smart_plugs = [
            WiserSmartPlug(data, plug.get("id"), "Wiser {}".format(plug.get("Name")))
            for plug in data.wiserhub.getSmartPlugs()
        ]
        async_add_entities(wiser_smart_plugs)

    @callback
    def set_smartplug_mode(service):
        entity_id = service.data[ATTR_ENTITY_ID]
        smart_plug_mode = service.data[ATTR_PLUG_MODE]

        _LOGGER.debug(
            "Set Smartplub called - entity %s mode %s ", entity_id, smart_plug_mode,
        )

        for smart_plug in wiser_smart_plugs:

            if smart_plug.entity_id == entity_id:
                hass.async_create_task(smart_plug.set_smartplug_mode(smart_plug_mode))
            smart_plug.schedule_update_ha_state(True)
            break

    @callback
    def set_hotwater_mode(service):
        hotwater_mode = service.data[ATTR_HOTWATER_MODE]
        hass.async_create_task(data.set_hotwater_mode(hotwater_mode))

    # Register Services
    hass.services.async_register(
        DOMAIN,
        WISER_SERVICES["SERVICE_SET_SMARTPLUG_MODE"],
        set_smartplug_mode,
        schema=SET_PLUG_MODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        WISER_SERVICES["SERVICE_SET_HOTWATER_MODE"],
        set_hotwater_mode,
        schema=SET_HOTWATER_MODE_SCHEMA,
    )
    return True


class WiserSwitch(SwitchEntity):
    """Switch to set the status of the Wiser Operation Mode (Away/Normal)."""

    def __init__(self, data, switchType, hubKey, icon):
        """Initialize the sensor."""
        _LOGGER.info("Wiser %s Switch Init", switchType)
        self.data = data
        self._hub_key = hubKey
        self._icon = icon
        self._switch_type = switchType
        self._away_temperature = None

    async def async_update(self):
        """Async Update to HA."""
        _LOGGER.debug("Wiser %s Switch Update requested", self._switch_type)
        if self._switch_type == "Away Mode":
            self._away_temperature = round(
                self.data.wiserhub.getSystem().get("AwayModeSetPointLimit") / 10, 1,
            )

    @property
    def name(self):
        """Return the name of the Device."""
        return "Wiser " + self._switch_type

    @property
    def icon(self):
        """Return icon."""
        return self._icon

    @property
    def unique_id(self):
        """Return uniqueId."""
        return f"{self._switch_type}-{self.name}"

    @property
    def device_info(self):
        """Return device specific attributes."""
        identifier = self.data.unique_id

        return {
            "identifiers": {(DOMAIN, identifier)},
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def device_state_attributes(self):
        """Return the device state attributes for the attribute card."""
        attrs = {}

        if self._switch_type == "Away Mode":
            attrs["AwayModeTemperature"] = self._away_temperature

        return attrs

    @property
    def is_on(self):
        """Return true if device is on."""
        status = self.data.wiserhub.getSystem().get(self._hub_key)
        _LOGGER.debug("%s: %s", self._switch_type, status)
        if self._switch_type == "Away Mode":
            return status and status.lower() == "away"
        return status

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        if self._switch_type == "Away Mode":
            await self.data.set_away_mode(True, self._away_temperature)
        else:
            await self.data.set_system_switch(self._hub_key, True)
        return True

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        if self._switch_type == "Away Mode":
            await self.data.set_away_mode(False, self._away_temperature)
        else:
            await self.data.set_system_switch(self._hub_key, False)
        return True

    async def async_added_to_hass(self):
        """Subscribe for update from the hub."""

        async def async_update_state():
            """Update sensor state."""
            await self.async_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, "WiserHubUpdateMessage", async_update_state
            )
        )


class WiserSmartPlug(SwitchEntity):
    """Plug SwitchEntity Class."""

    def __init__(self, data, plugId, name):
        """Initialize the sensor."""
        _LOGGER.info("Wiser %s SmartPlug Init", name)
        self.plug_name = name
        self.smart_plug_id = plugId
        self.data = data
        self._is_on = False

    @property
    def unique_id(self):
        """Return unique ID for the plug."""
        return f"{self.plug_name}-{self.smart_plug_id}"

    @property
    def icon(self):
        """Return icon for the plug."""
        return "mdi:power-socket-uk"

    @property
    def device_info(self):
        """Return device specific attributes."""
        identifier = None
        model = None

        identifier = self.unique_id
        model = self.data.wiserhub.getDevice(self.smart_plug_id).get("ModelIdentifier")

        return {
            "name": self.plug_name,
            "identifiers": {(DOMAIN, identifier)},
            "manufacturer": MANUFACTURER,
            "model": model,
        }

    @property
    def name(self):
        """Return the name of the SmartPlug."""
        return self.plug_name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        self._is_on = self.data.wiserhub.getSmartPlug(self.smart_plug_id).get(
            "OutputState"
        )

        _LOGGER.debug("Smartplug %s is currently %s", self.smart_plug_id, self._is_on)

        if self._is_on == "On":
            return True
        return False

    @property
    def device_state_attributes(self):
        """Return set of device state attributes."""
        attrs = {}
        device_data = self.data.wiserhub.getSmartPlug(self.smart_plug_id)
        attrs["ManualState"] = device_data.get("ManualState")
        attrs["Name"] = device_data.get("Name")
        attrs["Mode"] = device_data.get("Mode")
        attrs["AwayAction"] = device_data.get("AwayAction")
        attrs["OutputState"] = device_data.get("OutputState")
        attrs["ControlSource"] = device_data.get("ControlSource")
        attrs["ScheduledState"] = device_data.get("ScheduledState")
        return attrs

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.data.set_smart_plug_state(self.smart_plug_id, "On")
        return True

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.data.set_smart_plug_state(self.smart_plug_id, "Off")
        return True

    async def set_smartplug_mode(self, plug_mode):
        """Set the smartplug mode."""
        await self.data.set_smartplug_mode(self.smart_plug_id, plug_mode)
        return True

    async def async_added_to_hass(self):
        """Subscribe for update from the hub."""

        async def async_update_state():
            """Update sensor state."""
            await self.async_update_ha_state(False)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, "WiserHubUpdateMessage", async_update_state
            )
        )
