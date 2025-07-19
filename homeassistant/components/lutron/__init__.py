"""Component for interacting with a Lutron RadioRA 2 system."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any
import urllib.request

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .aiolip import LIP, LIPAction, LIPLedState, LIPMessage, LIPMode
from .const import (
    CONF_REFRESH_DATA,
    CONF_USE_AREA_FOR_DEVICE_NAME,
    CONF_USE_FULL_PATH,
    CONF_VARIABLE_IDS,
    DOMAIN,
    LUTRON_DATA_FILE,
)
from .lutron_db import Button, Led, LutronXmlDbParser, OccupancyGroup, Output, Sysvar

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.EVENT,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


class LutronException(Exception):
    """Top level module exception."""


class IntegrationIdExistsError(LutronException):
    """Asserted when there's an attempt to register a duplicate integration id."""


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
                vol.Required(CONF_REFRESH_DATA, default=True): cv.boolean,
                vol.Required(CONF_USE_FULL_PATH, default=False): cv.boolean,
                vol.Required(CONF_USE_AREA_FOR_DEVICE_NAME, default=False): cv.boolean,
                vol.Required(CONF_VARIABLE_IDS, default=""): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class LutronController:
    """Main Lutron Controller class.

    This object owns the connection to the controller, the rooms that exist in the
    network, handles dispatch of incoming status updates, etc.
    """

    def __init__(self, hass, host, user, password):
        """Initialize the Lutron controller."""
        self.hass = hass
        self.host = host
        self.lip = LIP()
        self.connected = False
        self.connect_lock = None
        self._subscribers: dict[
            tuple[int, int | None], list[Callable]
        ] = {}  # integration_id, component_number -> list of entities
        self.guid = None
        self.areas = []
        self.variables = []
        self._entity_map: dict[int, Any] = {}
        self.name = None

    async def connect(self):
        """Connect to the Lutron controller."""
        if self.connect_lock is None:
            self.connect_lock = asyncio.Lock()
        async with self.connect_lock:
            if not self.connected:
                await self.lip.async_connect(self.host)
                self.connected = True
                self.hass.loop.create_task(self.lip.async_run())
                self.lip.set_callback(self._dispatch_message)

    def subscribe(self, integration_id, component_number, callback):
        """Subscribe the callable for a specific integration_id. Can be multiple entities for the same integration (e.g. keypad leds)."""
        key = (integration_id, component_number)
        self._subscribers.setdefault(key, []).append(callback)

    def _dispatch_message(self, msg: LIPMessage):
        """Call the function in the subscriber entity."""
        key = (msg.integration_id, msg.component_number)

        for cb in self._subscribers.get(key, []):
            match (msg.mode, msg.action_number):
                case (
                    (LIPMode.OUTPUT, LIPAction.OUTPUT_LEVEL)
                    | (LIPMode.GROUP, LIPAction.GROUP_STATE)
                    | (LIPMode.SYSVAR, LIPAction.SYSVAR_STATE)
                    | (LIPMode.DEVICE, LIPAction.DEVICE_LED_STATE)
                ):
                    cb(msg.value)
                case (
                    LIPMode.OUTPUT,
                    LIPAction.OUTPUT_UNDOCUMENTED_29 | LIPAction.OUTPUT_UNDOCUMENTED_30,
                ):
                    pass
                case (LIPMode.DEVICE, _):
                    cb(msg.action_number)
                case _:
                    # Optionally log or handle unknown message types
                    _LOGGER.debug("Unhandled LIP message: %s", msg)

    async def action(self, mode: LIPMode, *args):
        """Send an action command."""
        await self.connect()
        await self.lip.action(mode, *args)

    async def query(self, mode: LIPMode, *args):
        """Send a query command."""
        await self.connect()
        await self.lip.query(mode, *args)

    async def stop(self):
        """Stop the connection to the controller."""
        if self.connected:
            await self.lip.async_stop()
            self.connected = False

    async def output_set_level(
        self, output_id: int, new_level: float, fade_time: str | None = None
    ) -> None:
        """Set the level of an output."""
        await self.action(
            LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_LEVEL, new_level, fade_time
        )

    async def output_get_level(self, output_id: int) -> None:
        """Query the level of an output."""
        await self.query(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_LEVEL)

    async def output_start_raising(self, output_id: int):
        """Start raising the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_START_RAISING)

    async def output_start_lowering(self, output_id: int):
        """Start lowering the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_START_LOWERING)

    async def output_stop(self, output_id: int):
        """Stop the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_STOP)

    async def output_jog_raise(self, output_id: int):
        """Jog raise the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_MOTOR_JOG_RAISE)

    async def output_jog_lower(self, output_id: int):
        """Jog lower the motor."""
        await self.action(LIPMode.OUTPUT, output_id, LIPAction.OUTPUT_MOTOR_JOG_LOWER)

    async def group_get_state(self, group_id: int) -> None:
        """Query the level of an output."""
        await self.query(LIPMode.GROUP, group_id, LIPAction.GROUP_STATE)

    async def device_press(self, keypad_id: int, component_number: int) -> None:
        """Triggers a simulated button press to the Keypad."""
        await self.action(
            LIPMode.DEVICE, keypad_id, component_number, LIPAction.DEVICE_PRESS
        )

    async def device_turn_on(self, keypad_id: int, component_number: int):
        """Turn on the LED."""
        await self.action(
            LIPMode.DEVICE,
            keypad_id,
            component_number,
            LIPAction.DEVICE_LED_STATE,
            LIPLedState.ON,
        )

    async def device_turn_off(self, keypad_id: int, component_number: int):
        """Turn off the LED."""
        await self.action(
            LIPMode.DEVICE,
            keypad_id,
            component_number,
            LIPAction.DEVICE_LED_STATE,
            LIPLedState.OFF,
        )

    async def device_get_state(self, keypad_id: int, component_number: int):
        """Get LED state."""
        await self.query(
            LIPMode.DEVICE, keypad_id, component_number, LIPAction.DEVICE_LED_STATE
        )

    async def sysvar_set_state(self, sysvar_id: int, value: int):
        """Set the variable."""
        await self.action(LIPMode.SYSVAR, sysvar_id, LIPAction.SYSVAR_STATE, value)

    async def sysvar_get_state(self, sysvar_id: int) -> None:
        """Get the Variable state."""
        await self.query(LIPMode.SYSVAR, sysvar_id, LIPAction.SYSVAR_STATE)

    def load_xml_db(self, cache_path=None, refresh_data=True, variable_ids=None):
        """Load the Lutron database from the server if refresh_data is True.

        If not, if a locally cached copy is available, use that instead, or
        create one and store it
        """

        xml_db = None
        loaded_from = None
        variable_ids = variable_ids or []

        if cache_path and not refresh_data:
            try:
                with Path.open(cache_path, "rb") as f:  # pylint: disable=unspecified-encoding
                    xml_db = f.read()
                    loaded_from = "cache"
            except OSError as e:
                _LOGGER.debug("Failed to read XML cache: %s", e)
        if not loaded_from:
            url = "http://" + self.host + "/DbXmlInfo.xml"
            with urllib.request.urlopen(url) as xmlfile:
                xml_db = xmlfile.read()
                loaded_from = "repeater"
                if cache_path and not refresh_data:
                    with Path.open(cache_path, "wb") as f:  # pylint: disable=unspecified-encoding
                        f.write(xml_db)
                        _LOGGER.info("Stored db as %s", cache_path)

        _LOGGER.info("Loaded xml db from %s", loaded_from)

        parser = LutronXmlDbParser(xml_db_str=xml_db, variable_ids=variable_ids)
        assert parser.parse()  # throw our own exception
        self.areas = parser.areas
        self.name = parser.project_name
        self.variables = parser.variables
        self.guid = parser.lutron_guid

        _LOGGER.info("Found Lutron project: %s, %d areas", self.name, len(self.areas))

        if cache_path and loaded_from == "repeater":
            with Path.open(cache_path, "wb") as f:  # pylint: disable=unspecified-encoding
                f.write(xml_db)

        return True


@dataclass(slots=True, kw_only=True)
class LutronData:
    """Storage class for platform global data."""

    controller: LutronController
    binary_sensors: list[tuple[str, OccupancyGroup]]
    covers: list[tuple[str, str, Output]]
    fans: list[tuple[str, str, Output]]
    lights: list[tuple[str, str, Output]]
    buttons: list[tuple[str, str, Button]]
    scenes: list[tuple[str, str, Button]]
    leds: list[tuple[str, str, Led]]
    switches: list[tuple[str, str, Output]]
    variables: list[tuple[str, Sysvar]]


def get_entry_value(entry: ConfigEntry, key: str, default=None):
    """Get the entry from options if available, else return it from the original data."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Lutron integration."""

    host = config_entry.data[CONF_HOST]
    uid = config_entry.data[CONF_USERNAME]
    pwd = config_entry.data[CONF_PASSWORD]
    refresh_data = get_entry_value(config_entry, CONF_REFRESH_DATA, True)
    use_full_path = get_entry_value(
        config_entry, CONF_USE_FULL_PATH, False
    )  # use also the location (i.e., the parent area) for the area name
    use_area_for_device_name = get_entry_value(
        config_entry, CONF_USE_AREA_FOR_DEVICE_NAME, False
    )  # use area name in the device name
    variable_ids_str = get_entry_value(config_entry, CONF_VARIABLE_IDS, "")
    variable_ids = [
        int(v.strip()) for v in variable_ids_str.split(",") if v.strip().isdigit()
    ]

    lutron_data_file = hass.config.path(LUTRON_DATA_FILE)

    lutron_controller = LutronController(hass, host, uid, pwd)
    await hass.async_add_executor_job(
        lambda: lutron_controller.load_xml_db(
            lutron_data_file, refresh_data, variable_ids=variable_ids
        )
    )
    await lutron_controller.connect()
    _LOGGER.info("Connected to main repeater at %s", host)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entry_data = LutronData(
        controller=lutron_controller,
        binary_sensors=[],
        buttons=[],
        covers=[],
        fans=[],
        lights=[],
        leds=[],
        scenes=[],
        switches=[],
        variables=[],
    )
    # Sort our devices into types
    _LOGGER.debug("Start adding devices")
    for area in lutron_controller.areas:
        area_name = area.name if not use_full_path else area.location + " " + area.name
        _LOGGER.debug("Working on area %s", area.name)
        for output in area.outputs:
            device_name = (
                output.name
                if not use_area_for_device_name
                else area_name + " " + output.name
            )
            _LOGGER.debug("Working on output %s", output.output_type)
            if output.is_motor or output.is_shade:
                entry_data.covers.append((area_name, device_name, output))
                platform = Platform.COVER
            elif output.is_fan:
                entry_data.fans.append((area_name, device_name, output))
                platform = Platform.FAN
            elif output.is_light:
                entry_data.lights.append((area_name, device_name, output))
                platform = Platform.LIGHT
            else:
                entry_data.switches.append((area_name, device_name, output))
                platform = Platform.SWITCH

            _async_check_entity_unique_id(
                hass,
                entity_registry,
                platform,
                output.uuid,
                output.legacy_uuid,
                entry_data.controller.guid,
            )
            _async_check_device_identifiers(
                hass,
                device_registry,
                output.uuid,
                output.legacy_uuid,
                entry_data.controller.guid,
            )

        for keypad in area.keypads:
            device_name = (
                keypad.name
                if not use_area_for_device_name
                else area_name + " " + keypad.name
            )
            for button in keypad.buttons:
                # If the button has a function assigned to it, add it as a scene
                # Add the button for the corresponding events
                # Add the leds if they are controlled by integration in Lutron
                if button.has_action:
                    entry_data.buttons.append((area_name, device_name, button))

                    _async_check_entity_unique_id(
                        hass,
                        entity_registry,
                        Platform.EVENT,
                        button.uuid,
                        button.legacy_uuid,
                        entry_data.controller.guid,
                    )

                    entry_data.scenes.append((area_name, device_name, button))

                    _async_check_entity_unique_id(
                        hass,
                        entity_registry,
                        Platform.SCENE,
                        button.uuid,
                        button.legacy_uuid,
                        entry_data.controller.guid,
                    )

                    # Associate an LED with a button if there is one
                    led = next(
                        (led for led in keypad.leds if led.number == button.number),
                        None,
                    )

                    # Add the LED as a light device if is controlled via integration
                    if led is not None and button.led_logic == 5:
                        entry_data.leds.append((area_name, device_name, led))

                        _async_check_entity_unique_id(
                            hass,
                            entity_registry,
                            Platform.LIGHT,
                            led.uuid,
                            led.legacy_uuid,
                            entry_data.controller.guid,
                        )
                else:
                    _LOGGER.debug(
                        "Button without action %s -  %s ", keypad.name, button.engraving
                    )

        # exclude occupancy_group not linked to an area
        if area.occupancy_group is not None and area.occupancy_group.id != 0:
            entry_data.binary_sensors.append((area_name, area.occupancy_group))
            platform = Platform.BINARY_SENSOR
            _async_check_entity_unique_id(
                hass,
                entity_registry,
                platform,
                area.occupancy_group.uuid,
                area.occupancy_group.legacy_uuid,
                entry_data.controller.guid,
            )
            _async_check_device_identifiers(
                hass,
                device_registry,
                area.occupancy_group.uuid,
                area.occupancy_group.legacy_uuid,
                entry_data.controller.guid,
            )
    # check variables
    for variable in lutron_controller.variables:
        _LOGGER.debug("Working on variable %s", variable.name)
        platform = Platform.SELECT
        entry_data.variables.append((variable.name, variable))

        _async_check_entity_unique_id(
            hass,
            entity_registry,
            platform,
            "",
            variable.legacy_uuid,
            entry_data.controller.guid,
        )
        _async_check_device_identifiers(
            hass,
            device_registry,
            "",
            variable.legacy_uuid,
            entry_data.controller.guid,
        )

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, lutron_controller.guid)},
        manufacturer="Lutron",
        name="Main repeater",
    )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = entry_data

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


def _async_check_entity_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: str,
    uuid: str,
    legacy_uuid: str,
    controller_guid: str,
) -> None:
    """If uuid becomes available update to use it."""

    if not uuid:
        return

    unique_id = f"{controller_guid}_{legacy_uuid}"
    entity_id = entity_registry.async_get_entity_id(
        domain=platform, platform=DOMAIN, unique_id=unique_id
    )

    if entity_id:
        new_unique_id = f"{controller_guid}_{uuid}"
        _LOGGER.debug("Updating entity id from %s to %s", unique_id, new_unique_id)
        entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)


def _async_check_device_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    uuid: str,
    legacy_uuid: str,
    controller_guid: str,
) -> None:
    """If uuid becomes available update to use it."""

    if not uuid:
        return

    unique_id = f"{controller_guid}_{legacy_uuid}"
    device = device_registry.async_get_device(identifiers={(DOMAIN, unique_id)})
    if device:
        new_unique_id = f"{controller_guid}_{uuid}"
        _LOGGER.debug("Updating device id from %s to %s", unique_id, new_unique_id)
        device_registry.async_update_device(
            device.id, new_identifiers={(DOMAIN, new_unique_id)}
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Clean up resources and entities associated with the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
