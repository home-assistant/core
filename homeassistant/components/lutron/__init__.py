"""Component for interacting with a Lutron RadioRA 2 system."""
from dataclasses import dataclass
import logging

from pylutron import Button, Keypad, Led, Lutron, LutronEvent, OccupancyGroup, Output
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import DOMAIN

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)

# Attribute on events that indicates what action was taken with the button.
ATTR_ACTION = "action"
ATTR_FULL_ID = "full_id"
ATTR_UUID = "uuid"

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


async def _async_import(hass: HomeAssistant, base_config: ConfigType) -> None:
    """Import a config entry from configuration.yaml."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=base_config[DOMAIN],
    )
    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "single_instance_allowed"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Lutron",
            },
        )
        return
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{result['reason']}",
        breaks_in_ha_version="2024.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Lutron",
        },
    )


async def async_setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up the Lutron component."""
    if DOMAIN in base_config:
        hass.async_create_task(_async_import(hass, base_config))
    return True


class LutronButton:
    """Representation of a button on a Lutron keypad.

    This is responsible for firing events as keypad buttons are pressed
    (and possibly released, depending on the button type). It is not
    represented as an entity; it simply fires events.
    """

    def __init__(
        self, hass: HomeAssistant, area_name: str, keypad: Keypad, button: Button
    ) -> None:
        """Register callback for activity on the button."""
        name = f"{keypad.name}: {button.name}"
        if button.name == "Unknown Button":
            name += f" {button.number}"
        self._hass = hass
        self._has_release_event = (
            button.button_type is not None and "RaiseLower" in button.button_type
        )
        self._id = slugify(name)
        self._keypad = keypad
        self._area_name = area_name
        self._button_name = button.name
        self._button = button
        self._event = "lutron_event"
        self._full_id = slugify(f"{area_name} {name}")
        self._uuid = button.uuid

        button.subscribe(self.button_callback, None)

    def button_callback(
        self, _button: Button, _context: None, event: LutronEvent, _params: dict
    ) -> None:
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
            data = {
                ATTR_ID: self._id,
                ATTR_ACTION: action,
                ATTR_FULL_ID: self._full_id,
                ATTR_UUID: self._uuid,
            }
            self._hass.bus.fire(self._event, data)


@dataclass(slots=True, kw_only=True)
class LutronData:
    """Storage class for platform global data."""

    client: Lutron
    binary_sensors: list[tuple[str, OccupancyGroup]]
    buttons: list[LutronButton]
    covers: list[tuple[str, Output]]
    fans: list[tuple[str, Output]]
    lights: list[tuple[str, Output]]
    scenes: list[tuple[str, Keypad, Button, Led]]
    switches: list[tuple[str, Output]]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Lutron integration."""

    host = config_entry.data[CONF_HOST]
    uid = config_entry.data[CONF_USERNAME]
    pwd = config_entry.data[CONF_PASSWORD]

    lutron_client = Lutron(host, uid, pwd)
    await hass.async_add_executor_job(lutron_client.load_xml_db)
    lutron_client.connect()
    _LOGGER.info("Connected to main repeater at %s", host)

    entry_data = LutronData(
        client=lutron_client,
        binary_sensors=[],
        buttons=[],
        covers=[],
        fans=[],
        lights=[],
        scenes=[],
        switches=[],
    )
    # Sort our devices into types
    _LOGGER.debug("Start adding devices")
    for area in lutron_client.areas:
        _LOGGER.debug("Working on area %s", area.name)
        for output in area.outputs:
            _LOGGER.debug("Working on output %s", output.type)
            if output.type == "SYSTEM_SHADE":
                entry_data.covers.append((area.name, output))
            elif output.type == "CEILING_FAN_TYPE":
                entry_data.fans.append((area.name, output))
                # Deprecated, should be removed in 2024.8
                entry_data.lights.append((area.name, output))
            elif output.is_dimmable:
                entry_data.lights.append((area.name, output))
            else:
                entry_data.switches.append((area.name, output))
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
                    entry_data.scenes.append((area.name, keypad, button, led))

                entry_data.buttons.append(LutronButton(hass, area.name, keypad, button))
        if area.occupancy_group is not None:
            entry_data.binary_sensors.append((area.name, area.occupancy_group))

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, lutron_client.guid)},
        manufacturer="Lutron",
        name="Main repeater",
    )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = entry_data

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Clean up resources and entities associated with the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
