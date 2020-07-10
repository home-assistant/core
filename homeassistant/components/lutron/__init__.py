"""Component for interacting with a Lutron RadioRA 2 system."""
import logging

from pylutron import Button, Lutron
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_ID, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import area_registry as ar, device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import CONF_ENABLE_AREAS, DEFAULT_ENABLE_AREAS, DOMAIN

_LOGGER = logging.getLogger(__name__)

LUTRON_BUTTONS = "lutron_buttons"
LUTRON_CONTROLLER = "lutron_controller"
LUTRON_DEVICES = "lutron_devices"

# Attribute on events that indicates what action was taken with the button.
ATTR_ACTION = "action"
ATTR_FULL_ID = "full_id"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, base_config):
    """Set up the Lutron component."""
    hass.data.setdefault(DOMAIN, {})
    config = base_config.get(DOMAIN)

    if config is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
            )
        )
    return True


class DummyArea:
    """Fake area object.

    This is used to tell all the lutron entities the names of the area they
    belong to when we don't want to force the creation of those areas.
    """

    def __init__(self, name):
        """Initialize the area."""
        self.name = name
        self.id = None


async def async_setup_entry(hass, entry):
    """Set up a single Lutron deployment."""
    if not entry.data:
        return False

    config = entry.data
    device_registry = await dr.async_get_registry(hass)
    area_registry = await ar.async_get_registry(hass)
    hass_data = {
        LUTRON_BUTTONS: {},
        LUTRON_CONTROLLER: None,
        LUTRON_DEVICES: {
            "light": [],
            "cover": [],
            "switch": [],
            "scene": [],
            "binary_sensor": [],
        },
    }
    hass.data[DOMAIN][entry.entry_id] = hass_data
    hass_data[LUTRON_CONTROLLER] = Lutron(
        config[CONF_HOST], config[CONF_USERNAME], config[CONF_PASSWORD]
    )

    await hass.async_add_executor_job(hass_data[LUTRON_CONTROLLER].load_xml_db)
    hass_data[LUTRON_CONTROLLER].connect()
    _LOGGER.info("Connected to main repeater at %s", config[CONF_HOST])

    # Sort our devices into types
    for area in hass_data[LUTRON_CONTROLLER].areas:
        if entry.options.get(CONF_ENABLE_AREAS, DEFAULT_ENABLE_AREAS):
            hass_area = area_registry.async_get_or_create(area.name)
        else:
            hass_area = DummyArea(area.name)
        for output in area.outputs:
            if output.type == "SYSTEM_SHADE":
                hass_data[LUTRON_DEVICES]["cover"].append((hass_area, output))
            elif output.is_dimmable:
                hass_data[LUTRON_DEVICES]["light"].append((hass_area, output))
            else:
                hass_data[LUTRON_DEVICES]["switch"].append((hass_area, output))
        for keypad in area.keypads:
            for button in keypad.buttons:
                # If the button has a function assigned to it, add it as a scene
                if button.name != "Unknown Button" and button.button_type in (
                    "SingleAction",
                    "Toggle",
                    "SingleSceneRaiseLower",
                    "MasterRaiseLower",
                ):
                    # Associate an LED with a button if there is one
                    led = next(
                        (led for led in keypad.leds if led.number == button.number),
                        None,
                    )
                    hass_data[LUTRON_DEVICES]["scene"].append(
                        (hass_area, keypad, button, led)
                    )

                hass_button = LutronButton(hass, hass_area, keypad, button)
                _LOGGER.debug("Adding Button %s", hass_button.id)
                hass_data[LUTRON_BUTTONS][hass_button.id] = hass_button
        if area.occupancy_group is not None and area.sensors:
            hass_data[LUTRON_DEVICES]["binary_sensor"].append(
                (hass_area, area.occupancy_group)
            )

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        # connections={(dr.CONNECTION_NETWORK_MAC, config.mac)},
        identifiers={(DOMAIN, hass_data[LUTRON_CONTROLLER].guid)},
        manufacturer="Lutron",
        name=hass_data[LUTRON_CONTROLLER].name,
        # model=config.modelid,
        # sw_version=config.swversion,
    )

    _LOGGER.debug("Loading Components")
    for component in ("light", "cover", "switch", "scene", "binary_sensor"):
        _LOGGER.debug("Loading %s", component)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    _LOGGER.debug("Setup Services!!!")
    setup_services(hass, hass_data)
    _LOGGER.debug("Setup Entry returning true...")
    return True


ATTR_NAME = "button"


def setup_services(hass, hass_data):
    """Create Lutron specific services."""

    def handle_press_button(call):
        """Handle a press button service call."""
        button_id = call.data.get(ATTR_NAME)
        button = hass_data[LUTRON_BUTTONS].get(button_id, None)
        if button:
            button.press()

    def handle_release_button(call):
        """Handle a press button service call."""
        button_id = call.data.get(ATTR_NAME)
        button = hass_data[LUTRON_BUTTONS].get(button_id, None)
        if button:
            button.release()

    def handle_tap_button(call):
        """Handle a press button service call."""
        button_id = call.data.get(ATTR_NAME)
        button = hass_data[LUTRON_BUTTONS].get(button_id, None)
        if button:
            button.tap()

    hass.services.async_register(DOMAIN, "press_button", handle_press_button)
    hass.services.async_register(DOMAIN, "release_button", handle_release_button)
    hass.services.async_register(DOMAIN, "tap_button", handle_tap_button)


class LutronDevice(Entity):
    """Representation of a Lutron device entity."""

    def __init__(self, area, lutron_device, controller):
        """Initialize the device."""
        self._lutron_device = lutron_device
        self._controller = controller
        self._area = area

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.async_add_executor_job(
            self._lutron_device.subscribe, self._update_callback, None
        )

    def _update_callback(self, _device, _context, _event, _params):
        """Run when invoked by pylutron when the device state changes."""
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        if self._area.id:
            return self._lutron_device.name
        return f"{self._area.name} {self._lutron_device.name}"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return a unique ID."""
        # Note: At this time, occupancy sensors don't generate unique IDs.
        return f"{self._controller.guid}_{self._lutron_device.uuid}"

    @property
    def device_info(self):
        """Return key information on the device."""
        device_info = {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": "Lutron",
            # "model": self.light.productname,
            # "sw_version": self.light.swversion,
            "via_device": (DOMAIN, self._controller.guid),
        }
        if self._area.id:
            device_info["area_id"] = self._area.id
        return device_info


class LutronButton:
    """Representation of a button on a Lutron keypad.

    This is responsible for firing events as keypad buttons are pressed
    (and possibly released, depending on the button type). It is not
    represented as an entity.

    In addition to firing events, it supports button events.  This is most
    useful for Alarm style buttons where the system will stay in an alarm
    state while a button is pressed and reset once the button is released.
    """

    def __init__(self, hass, area, keypad, button):
        """Register callback for activity on the button."""
        name = f"{keypad.name}: {button.name}"
        self._hass = hass
        self._has_release_event = (
            button.button_type is not None and "RaiseLower" in button.button_type
        )
        self._id = slugify(name)
        self._keypad = keypad
        self._area = area
        self._button_name = button.name
        self._button = button
        self._event = "lutron_event"
        self._full_id = slugify(f"{area.name} {keypad.name}: {button.name}")

        button.subscribe(self.button_callback, None)

    @property
    def id(self):
        """ID of the button."""
        return self._id

    def press(self):
        """Press (and hold) a button."""
        self._button.press()

    def release(self):
        """Release a button."""
        self._button.release()

    def tap(self):
        """Press and release a button."""
        self._button.tap()

    def button_callback(self, button, context, event, params):
        """Fire an event about a button being pressed or released."""
        # Events per button type:
        #   RaiseLower -> pressed/released
        #   SingleAction -> single
        action = None
        if self._has_release_event:
            if event == Button.Event.PRESSED:
                action = "pressed"
            else:
                action = "released"
        elif event == Button.Event.PRESSED:
            action = "single"

        if action:
            data = {ATTR_ID: self._id, ATTR_ACTION: action, ATTR_FULL_ID: self._full_id}
            self._hass.bus.fire(self._event, data)
