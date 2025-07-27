"""Lutron RadioRA 2 and HomeWorks QS module for parsing the Lutron DB.

Return all the devices in the system

Original work from https://github.com/thecynic/pylutron
Author Dima Zavin
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any

import defusedxml.ElementTree as ET

if TYPE_CHECKING:
    from . import LutronController

from .data import LIPAction, LIPLedState, LIPMode

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class LutronXmlDbParser:
    """The parser for Lutron XML database.

    The database describes all the rooms (Area), keypads (Device), and switches
    (Output). We handle the most relevant features, but some things like LEDs,
    etc. are not implemented.
    """

    def __init__(self, xml_db_str, variable_ids, controller=None):
        """Initialize the XML parser, takes the raw XML data as string input."""
        self._xml_db_str = xml_db_str
        self.areas = []
        self.variables = []
        self._occupancy_groups = {}
        self.project_name = None
        self._variables_ids = variable_ids
        self.lutron_guid = None
        self._controller = controller  # Store controller reference

    def parse(self):
        """Create the Main entrypoint into the parser.

        It interprets and creates all the relevant Lutron objects and stuffs them into the appropriate hierarchy.
        """

        def visit_area(area_to_visit, location=None):
            for areas_xml in area_to_visit.findall("Areas"):
                for area_xml in areas_xml.findall("Area"):
                    area = self._parse_area(area_xml, location)
                    self.areas.append(area)
                    visit_area(area_xml, area.name)

        root = ET.fromstring(self._xml_db_str)
        # The structure is something like this:
        # <Areas>
        #   <Area ...>
        #     <DeviceGroups ...>
        #     <Scenes ...>
        #     <ShadeGroups ...>
        #     <Outputs ...>
        #     <Areas ...>
        #       <Area ...>

        # The GUID is unique to the repeater and is useful for constructing unique
        # identifiers that won't change over time.
        self.lutron_guid = root.find("GUID").text

        # Parse Occupancy Groups
        # OccupancyGroups are referenced by entities in the rest of the XML.  The
        # current structure of the code expects to go from areas -> devices ->
        # other assets and attributes.  Here we index the groups to be bound to
        # Areas later.
        groups = root.find("OccupancyGroups")
        for group_xml in groups.iter("OccupancyGroup"):
            group = self._parse_occupancy_group(group_xml)
            if group.group_number:
                self._occupancy_groups[group.group_number] = group
            else:
                _LOGGER.warning("Occupancy Group has no number.  XML: %s", group_xml)

        # First area is useless, it's the top-level project area that defines the
        # "house". It contains the real nested Areas tree, which is the one we want.
        top_area = root.find("Areas").find("Area")
        self.project_name = top_area.get("Name")
        visit_area(top_area)
        for variable in self._variables_ids:
            self.variables.append(self._parse_sysvar(variable))
        return True

    def _parse_area(self, area_xml, location):
        """Parse an Area tag, which is effectively a room, depending on how the Lutron controller programming was done."""
        location = location or ""
        name = area_xml.get("Name")
        occupancy_group_id = area_xml.get("OccupancyGroupAssignedToID")
        occupancy_group = self._occupancy_groups.get(occupancy_group_id)
        if occupancy_group_id and not occupancy_group:
            _LOGGER.warning(
                "Occupancy Group not found for Area: %s; ID: %s",
                name,
                occupancy_group_id,
            )
        area = Area(
            name=name,
            location=location,
            integration_id=int(area_xml.get("IntegrationID")),
            occupancy_group=occupancy_group,
        )
        for output_xml in area_xml.find("Outputs"):
            output = self._parse_output(area, output_xml)
            area.add_output(output)

        # device group in our case means keypad
        # device_group.get('Name') is the name of the device
        for device_group in area_xml.find("DeviceGroups"):
            if device_group.tag == "DeviceGroup":
                devs = device_group.find("Devices")
            elif device_group.tag == "Device":
                # device that is not a keypad, e.g. QS_IO_INTERFACE
                devs = [device_group]
            else:
                _LOGGER.info("Unknown tag in DeviceGroups child %s", device_group.tag)
                devs = []
            for device_xml in devs:
                if device_xml.tag != "Device":
                    continue
                if (device_type := device_xml.get("DeviceType")) is None:
                    # phantom keypad doesn't have a DeviceType
                    device_type = "PHANTOM"
                if device_type in (
                    "PHANTOM",
                    "HWI_SEETOUCH_KEYPAD",
                    "SEETOUCH_KEYPAD",
                    "SEETOUCH_TABLETOP_KEYPAD",
                    "PICO_KEYPAD",
                    "HYBRID_SEETOUCH_KEYPAD",
                    "MAIN_REPEATER",
                    "HOMEOWNER_KEYPAD",
                    "INTERNATIONAL_SEETOUCH_KEYPAD",
                    "WCI",
                    "QS_IO_INTERFACE",
                    "GRAFIK_T_HYBRID_KEYPAD",
                    "HWI_SLIM",
                ):
                    keypad = self._parse_keypad(
                        area, device_xml, device_group, device_type
                    )
                    area.add_keypad(keypad)
                elif device_xml.get("DeviceType") == "MOTION_SENSOR":
                    motion_sensor = self._parse_motion_sensor(area, device_xml)
                    area.add_sensor(motion_sensor)
                else:
                    _LOGGER.warning(
                        "Unknown %s Device type", device_xml.get("DeviceType")
                    )

        return area

    def _parse_output(self, area, output_xml):
        """Parse an output, which is generally a switch controlling a set of lights/outlets, etc."""
        kwargs = {
            "area": area,
            "name": output_xml.get("Name"),
            "watts": int(output_xml.get("Wattage")),
            "output_type": output_xml.get("OutputType"),
            "integration_id": int(output_xml.get("IntegrationID")),
            "uuid": output_xml.get("UUID"),
        }
        output = Output(**kwargs)
        output.controller = self._controller
        return output

    def _parse_keypad(self, area, keypad_xml, device_group, device_type):
        """Parse a keypad device (the Visor receiver is technically a keypad too)."""
        # in HWs the keypad standard name is CSD 001
        # Note that device_group.get('Name') is the real name of the keypad and motion sensor
        name = keypad_xml.get("Name")
        device_group_name = device_group.get("Name")
        keypad = Keypad(
            area=area,
            name=name,
            device_type=device_type,
            device_group_name=device_group_name,
            integration_id=int(keypad_xml.get("IntegrationID")),
            uuid=keypad_xml.get("UUID"),
        )
        keypad.controller = self._controller
        components = keypad_xml.find("Components")
        if components is None:
            return keypad
        for comp in components:
            if comp.tag != "Component":
                continue
            comp_type = comp.get("ComponentType")
            if comp_type == "BUTTON":
                button = self._parse_button(keypad, comp)
                keypad.add_button(button)
            elif comp_type == "CCI":
                button = self._parse_cci(keypad, comp)
                keypad.add_button(button)
            elif comp_type == "LED":
                led = self._parse_led(keypad, comp)
                keypad.add_led(led)
        return keypad

    def _parse_button(self, keypad, component_xml):
        """Parse a button device that part of a keypad.

        'Name' is Button x, where x is incremental position in the list and not the actual position on the keypad.
        We don't use it. We use component_number instead
        """
        # we should read button - actions  - action to get available button actions

        component_number = int(component_xml.get("ComponentNumber"))
        button_xml = component_xml.find("Button")
        name = button_xml.get("Engraving")
        engraving = button_xml.get("Engraving")
        button_type = button_xml.get("ButtonType")
        direction = button_xml.get("Direction")
        led_logic = int(button_xml.get("LedLogic") or 0)

        # Hybrid keypads have dimmer buttons which have no engravings.
        if button_type == "SingleSceneRaiseLower":
            name = "Dimmer " + direction
        # a button without engraving can be a valid button (e.g., keypad lower/raiser buttons)
        if not name:
            name = f"Unknown Button {component_number}"

        return Button(
            keypad=keypad,
            name=name,
            engraving=engraving,
            number=component_number,
            component_number=component_number,
            button_type=button_type,
            direction=direction,
            led_logic=led_logic,
            integration_id=keypad.id,
            uuid=button_xml.get("UUID"),
        )

    def _parse_cci(self, keypad, component_xml):
        """Parse a cci (contact closure input) device that part of a keypad."""
        component_number = int(component_xml.get("ComponentNumber"))
        cci_xml = component_xml.find("CCI")
        cci_type = cci_xml.get("ButtonType")
        led_logic = cci_xml.get("LedLogic")
        name = f"CCI {component_number}"
        return Button(
            keypad=keypad,
            name=name,
            engraving="",
            number=component_number,
            component_number=component_number,
            button_type=cci_type,
            direction="",
            led_logic=led_logic,
            integration_id=keypad.id,
            uuid=cci_xml.get("UUID"),
        )

    def _parse_led(self, keypad, component_xml):
        """Parse an LED device that part of a keypad."""
        component_num = int(component_xml.get("ComponentNumber"))
        led_base = 80
        if keypad.device_type == "MAIN_REPEATER":
            led_base = 100
        elif keypad.device_type == "PHANTOM":
            led_base = 2000
        led_num = component_num - led_base
        name = f"LED {led_num}"
        return Led(
            keypad=keypad,
            name=name,
            number=led_num,
            component_number=component_num,
            integration_id=keypad.id,
            uuid=component_xml.find("LED").get("UUID"),
        )

    def _parse_motion_sensor(self, area, sensor_xml):
        """Parse a motion sensor object.

        TODO: We don't actually do anything with these yet. There's a lot of info
        that needs to be managed to do this right. We'd have to manage the occupancy
        groups, what's assigned to them, and when they go (un)occupied. We'll handle
        this later.
        """
        sensor = MotionSensor(
            area=area,
            name=sensor_xml.get("Name"),
            integration_id=int(sensor_xml.get("IntegrationID")),
            uuid=sensor_xml.get("UUID"),
        )
        sensor.controller = self._controller
        return sensor

    def _parse_occupancy_group(self, group_xml):
        """Parse an Occupancy Group object.

        These are defined outside the areas in the XML.  Areas refer to these
        objects by ID.
        OccupancyGroup gets the integration_id from the area
        """
        occupancy_group = OccupancyGroup(
            name="Occupancy Group",
            integration_id=0,
            group_number=group_xml.get("OccupancyGroupNumber"),
            uuid=group_xml.get("UUID"),
        )
        occupancy_group.controller = self._controller
        return occupancy_group

    def _parse_sysvar(self, integration_id):
        """Create a Sysvar object.

        We only have the integration_id available here, so we use that.
        """
        sysvar = Sysvar(
            name=f"variable {integration_id}", integration_id=integration_id, uuid=None
        )
        sysvar.controller = self._controller
        return sysvar


class Area:
    """An area (i.e. a room) that contains devices/outputs/etc."""

    def __init__(self, name, location, integration_id, occupancy_group):
        """Initialize the area."""
        self._name = name
        self._location = location
        self._integration_id = integration_id
        self._occupancy_group = occupancy_group
        self._outputs = []
        self._keypads = []
        self._sensors = []
        if occupancy_group:
            occupancy_group.bind_area(self)

    def add_output(self, output):
        """Add an output object that's part of this area, only used during initial parsing."""
        self._outputs.append(output)

    def add_keypad(self, keypad):
        """Add a keypad object that's part of this area, only used during initial parsing."""
        self._keypads.append(keypad)

    def add_sensor(self, sensor):
        """Add a motion sensor object that's part of this area, only used during initial parsing."""
        self._sensors.append(sensor)

    @property
    def name(self):
        """Returns the name of this area."""
        return self._name

    @property
    def location(self):
        """Returns the location of this area which is the name of the parent area or the empty string."""
        return self._location

    @property
    def id(self):
        """The integration id of the area."""
        return self._integration_id

    @property
    def occupancy_group(self):
        """Returns the OccupancyGroup for this area, or None."""
        return self._occupancy_group

    @property
    def outputs(self):
        """Return the tuple of the Outputs from this area."""
        return tuple(output for output in self._outputs)

    @property
    def keypads(self):
        """Return the tuple of the Keypads from this area."""
        return tuple(keypad for keypad in self._keypads)

    @property
    def sensors(self):
        """Return the tuple of the MotionSensors from this area."""
        return tuple(sensor for sensor in self._sensors)


@dataclass
class Device:
    """Base class for all the Lutron objects we'd like to manage."""

    name: str
    uuid: str | None
    integration_id: int
    area: Area | None = None
    legacy_uuid: str | None = field(init=False, default=None)
    _controller: LutronController | None = field(init=False, default=None)

    def __post_init__(self):
        """Override to Initialize the Lutron entity."""
        self.legacy_uuid = f"{self.integration_id}-0"

    @property
    def controller(self) -> LutronController:
        """Get the controller instance.

        Raises:
            RuntimeError: If controller is not set

        """
        if self._controller is None:
            raise RuntimeError(
                f"Controller not set on device {self.name} (ID: {self.integration_id})"
            )
        return self._controller

    @controller.setter
    def controller(self, value: LutronController) -> None:
        """Set the controller instance."""
        self._controller = value

    @property
    def id(self) -> int:
        """Return the integration ID."""
        return self.integration_id


@dataclass
class Output(Device):
    """Output entity in Lutron universe.

    This generally refers to a switched/dimmed load, e.g. light fixture, outlet, etc.
    """

    watts: int = 0
    output_type: str = ""

    is_dimmable: bool = field(init=False, default=False)
    is_light: bool = field(init=False, default=False)
    is_shade: bool = field(init=False, default=False)
    is_motor: bool = field(init=False, default=False)
    is_fan: bool = field(init=False, default=False)
    is_switch: bool = field(init=False, default=False)

    def __post_init__(self):
        """Set the type of OUTPUT."""
        super().__post_init__()

        t = self.output_type

        if t.startswith("CCO_") or t in {
            "RELAY_LIGHTING",
            "EXHAUST_FAN_TYPE",
            "SWITCHED_MOTOR",
        }:
            self.is_switch = True
        elif t == "SYSTEM_SHADE":
            self.is_shade = True
        elif t.startswith("MOTOR"):
            self.is_motor = True
        elif t == "CEILING_FAN_TYPE":
            self.is_fan = True
        else:
            self.is_light = True
            self.is_dimmable = not t.startswith("NON_DIM")

    async def set_level(self, level: float, fade_time: str | None = None) -> None:
        """Set the output level."""
        await self.controller.action(
            LIPMode.OUTPUT,
            self.integration_id,
            LIPAction.OUTPUT_LEVEL,
            level,
            fade_time,
        )

    async def get_level(self) -> None:
        """Get the current output level."""
        await self.controller.query(
            LIPMode.OUTPUT, self.integration_id, LIPAction.OUTPUT_LEVEL
        )

    async def start_raising(self) -> None:
        """Start raising the motor."""
        await self.controller.action(
            LIPMode.OUTPUT, self.integration_id, LIPAction.OUTPUT_START_RAISING
        )

    async def start_lowering(self) -> None:
        """Start lowering the motor."""
        await self.controller.action(
            LIPMode.OUTPUT, self.integration_id, LIPAction.OUTPUT_START_LOWERING
        )

    async def stop(self) -> None:
        """Stop the motor."""
        await self.controller.action(
            LIPMode.OUTPUT, self.integration_id, LIPAction.OUTPUT_STOP
        )

    async def jog_raise(self) -> None:
        """Start raising the motor."""
        await self.controller.action(
            LIPMode.OUTPUT, self.integration_id, LIPAction.OUTPUT_MOTOR_JOG_RAISE
        )

    async def jog_lower(self) -> None:
        """Start lowering the motor."""
        await self.controller.action(
            LIPMode.OUTPUT, self.integration_id, LIPAction.OUTPUT_MOTOR_JOG_LOWER
        )


@dataclass
class KeypadComponent(Device):
    """Base class for keypad components (buttons, LEDs, etc.).

    The integration_id is the keypad ID.
    The lutron component number is referenced in commands and
    events. This is different from KeypadComponent.number because this property
    is only used for interfacing with the controller.
    """

    keypad: Any = None
    number: int = 0  # user-friendly number
    component_number: int = 0  # lutron internal number

    def __post_init__(self):
        """Set the legacy UUID and area for keypad components."""
        self.area = self.keypad.area
        self.legacy_uuid = f"{self.integration_id}-{self.component_number}"

    @property
    def controller(self) -> LutronController:
        """Get the controller instance. For a keypad component is the keypad controller."""
        if self.keypad.controller is None:
            raise RuntimeError(
                f"Controller not set on device {self.name} (ID: {self.integration_id})(Component: {self.component_number}"
            )
        return self.keypad.controller

    @controller.setter
    def controller(self, value: LutronController) -> None:
        """Set the controller instance."""
        self.keypad.controller = value


@dataclass
class Button(KeypadComponent):
    """Object representing a keypad button."""

    engraving: str = ""
    button_type: str = ""
    direction: str = ""
    led_logic: int = 0
    has_action: bool = field(init=False)

    def __post_init__(self):
        """Set if the Button has action."""
        super().__post_init__()
        self.has_action = self.button_type in (
            "SingleAction",
            "Toggle",
            "SingleSceneRaiseLower",
            "MasterRaiseLower",
            "DualAction",
            "AdvancedToggle",
            "AdvancedConditional",
            "SimpleConditional",
        )

    async def press(self) -> None:
        """Simulate a button press."""
        await self.keypad.controller.action(
            LIPMode.DEVICE,
            self.integration_id,
            self.component_number,
            LIPAction.DEVICE_PRESS,
        )


@dataclass
class Led(KeypadComponent):
    """Object representing a keypad LED."""

    async def turn_on(self) -> None:
        """Turn on the LED."""
        await self.controller.action(
            LIPMode.DEVICE,
            self.integration_id,
            self.component_number,
            LIPAction.DEVICE_LED_STATE,
            LIPLedState.ON,
        )

    async def turn_off(self) -> None:
        """Turn off the LED."""
        await self.controller.action(
            LIPMode.DEVICE,
            self.integration_id,
            self.component_number,
            LIPAction.DEVICE_LED_STATE,
            LIPLedState.OFF,
        )

    async def get_state(self) -> None:
        """Get the LED state."""
        await self.controller.query(
            LIPMode.DEVICE,
            self.integration_id,
            self.component_number,
            LIPAction.DEVICE_LED_STATE,
        )


@dataclass
class Keypad(Device):
    """Object representing a Lutron keypad."""

    device_type: str | None = None
    device_group_name: str | None = None
    buttons: list = field(default_factory=list)
    leds: list = field(default_factory=list)
    components: dict[int, Any] = field(default_factory=dict, repr=False)

    def add_button(self, button: Button):
        """Add a button that's part of this keypad."""
        self.buttons.append(button)
        self.components[button.component_number] = button

    def add_led(self, led: Led):
        """Add an LED that's part of this keypad."""
        self.leds.append(led)
        self.components[led.component_number] = led


class MotionSensor(Device):
    """Placeholder class for the motion sensor device.

    Although sensors are represented in the XML, all the protocol
    happens at the OccupancyGroup level. To read the state of an area,
    use area.occupancy_group.

    _CMD_TYPE = 'DEVICE'

    _ACTION_BATTERY_STATUS = 22
    """


@dataclass
class OccupancyGroup(Device):
    """Represents one or more occupancy/vacancy sensors grouped into an Area."""

    area: Any = None
    group_number: str | None = None

    def bind_area(self, area):
        """Binds the OccupancyGroup to the Area."""
        self.area = area
        self.legacy_uuid = f"{self.area.id}-{self.group_number}"
        self.name = f"Occ {area.name}"
        self.integration_id = area.id

    async def get_state(self) -> None:
        """Get the LED state."""
        await self.controller.query(
            LIPMode.GROUP, self.integration_id, LIPAction.GROUP_STATE
        )


@dataclass
class Sysvar(Device):
    """Represents one or more occupancy/vacancy sensors grouped into an Area."""

    async def set_state(self, value: int) -> None:
        """Set the system variable state."""
        await self.controller.action(
            LIPMode.SYSVAR, self.integration_id, LIPAction.SYSVAR_STATE, value
        )

    async def get_state(self) -> None:
        """Get the system variable state."""
        await self.controller.query(
            LIPMode.SYSVAR, self.integration_id, LIPAction.SYSVAR_STATE
        )
