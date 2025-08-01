"""Lutron RadioRA 2 and HomeWorks QS module for parsing the Lutron DB.

Return all the devices in the system

Original work from https://github.com/thecynic/pylutron
Author Dima Zavin
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, ClassVar, Protocol

import defusedxml.ElementTree as ET

from .data import LIPAction, LIPCommand, LIPLedState, LIPMode, LIPOperation

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
        self.lutron_guid = ""
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
        return Output(**kwargs)

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
        # Associate an LED with a button if there is one
        # and assign the same name as the button
        for button in keypad.buttons:
            led = next(
                (led for led in keypad.leds if led.number == button.number),
                None,
            )
            if led:
                led.button = button
                led.name = button.name

        return keypad

    def _parse_button_actions(self, button_xml):
        """Parse a button to return the list of actions."""
        actions = button_xml.find("Actions")

        # Extract names of all <Action> elements
        if actions is not None:
            return [
                action.get("Name")
                for action in actions.findall("Action")
                if action.get("Name")
            ]
        return []

    def _parse_button(self, keypad, component_xml):
        """Parse a button device that part of a keypad.

        'Name' is Button x, where x is incremental position in the list and not the actual position on the keypad.
        We don't use it. We use component_number instead
        """

        component_number = int(component_xml.get("ComponentNumber"))
        button_xml = component_xml.find("Button")
        actions = self._parse_button_actions(button_xml)
        return Button(
            keypad=keypad,
            component_type="Btn",
            name=button_xml.get("Name"),
            engraving=button_xml.get("Engraving"),
            component_number=component_number,
            button_type=button_xml.get("ButtonType"),
            direction=button_xml.get("Direction"),
            led_logic=int(button_xml.get("LedLogic") or 0),
            integration_id=keypad.integration_id,
            actions=actions,
            uuid=button_xml.get("UUID"),
        )

    def _parse_cci(self, keypad, component_xml):
        """Parse a cci (contact closure input) device that part of a keypad."""
        component_number = int(component_xml.get("ComponentNumber"))
        cci_xml = component_xml.find("CCI")
        actions = self._parse_button_actions(cci_xml)
        return Button(
            keypad=keypad,
            component_type="CCI",
            name="",
            engraving="",
            component_number=component_number,
            button_type=cci_xml.get("ButtonType"),
            direction="",
            led_logic=cci_xml.get("LedLogic"),
            integration_id=keypad.integration_id,
            actions=actions,
            uuid=cci_xml.get("UUID"),
        )

    def _parse_led(self, keypad, component_xml):
        """Parse an LED device that part of a keypad."""
        component_num = int(component_xml.get("ComponentNumber"))
        return Led(
            keypad=keypad,
            component_type="Led",
            name="",
            component_number=component_num,
            integration_id=keypad.integration_id,
            uuid=component_xml.find("LED").get("UUID"),
        )

    def _parse_motion_sensor(self, area, sensor_xml):
        """Parse a motion sensor object.

        TODO: We don't actually do anything with these yet. There's a lot of info
        that needs to be managed to do this right. We'd have to manage the occupancy
        groups, what's assigned to them, and when they go (un)occupied. We'll handle
        this later.
        """
        return MotionSensor(
            area=area,
            name=sensor_xml.get("Name"),
            integration_id=int(sensor_xml.get("IntegrationID")),
            uuid=sensor_xml.get("UUID"),
        )

    def _parse_occupancy_group(self, group_xml):
        """Parse an Occupancy Group object.

        These are defined outside the areas in the XML.  Areas refer to these
        objects by ID.
        OccupancyGroup gets the integration_id from the area
        """
        return OccupancyGroup(
            name="Occupancy Group",
            integration_id=0,
            group_number=group_xml.get("OccupancyGroupNumber"),
            uuid=group_xml.get("UUID"),
        )

    def _parse_sysvar(self, integration_id):
        """Create a Sysvar object.

        We only have the integration_id available here, so we use that.
        """
        return Sysvar(
            name=f"variable {integration_id}", integration_id=integration_id, uuid=None
        )


@dataclass
class Area:
    """An area (i.e. a room) that contains devices/outputs/etc."""

    name: str
    location: str
    integration_id: int
    occupancy_group: OccupancyGroup | None = None

    # Internal collections are not part of the dataclass constructor
    _outputs: list = field(default_factory=list, init=False, repr=False)
    _keypads: list = field(default_factory=list, init=False, repr=False)
    _sensors: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        """Bind the occupancy group to this area after initialization."""
        if self.occupancy_group:
            self.occupancy_group.bind_area(self)

    # Methods used by the XML parser during object graph construction
    def add_output(self, output):
        """Add an output object that's part of this area (used during initial parsing)."""
        self._outputs.append(output)

    def add_keypad(self, keypad):
        """Add a keypad object that's part of this area (used during initial parsing)."""
        self._keypads.append(keypad)

    def add_sensor(self, sensor):
        """Add a motion sensor object that's part of this area (used during initial parsing)."""
        self._sensors.append(sensor)

    # Convenience properties -------------------------------------------------
    @property
    def id(self) -> int:
        """The integration id of the area."""
        return self.integration_id

    @property
    def outputs(self):
        """Return a tuple of the outputs belonging to this area."""
        return tuple(self._outputs)

    @property
    def keypads(self):
        """Return a tuple of the keypads belonging to this area."""
        return tuple(self._keypads)

    @property
    def sensors(self):
        """Return a tuple of the motion sensors belonging to this area."""
        return tuple(self._sensors)


class LIPCommandSupporting(Protocol):
    """Mixin providing LIP command attributes."""

    LIP_MODE: ClassVar[LIPMode]
    integration_id: int
    component_number: int | None


class LIPCommandMixin:
    """Mixin providing LIP command creation methods."""

    def _query(
        self: LIPCommandSupporting,
        action: LIPAction,
    ) -> LIPCommand:
        """Create a query command."""
        return LIPCommand(
            operation=LIPOperation.QUERY,
            mode=self.LIP_MODE,
            integration_id=self.integration_id,
            component_number=getattr(self, "component_number", None),
            action=action,
        )

    def _execute(
        self: LIPCommandSupporting,
        action: LIPAction,
        value: float | None = None,
        fade_time: str | None = None,
    ) -> LIPCommand:
        """Create an execute command."""
        return LIPCommand(
            operation=LIPOperation.EXECUTE,
            mode=self.LIP_MODE,
            integration_id=self.integration_id,
            component_number=getattr(self, "component_number", None),
            action=action,
            value=value,
            fade_time=fade_time,
        )


@dataclass
class Device(LIPCommandMixin, LIPCommandSupporting):
    """Base class for all the Lutron objects we'd like to manage."""

    name: str
    uuid: str | None
    integration_id: int
    area: Area | None = None
    legacy_uuid: str = field(init=False, default="")

    LIP_MODE: ClassVar[LIPMode] = LIPMode.UNKNOWN  # Override in subclasses

    def __post_init__(self):
        """Override to Initialize the Lutron entity."""
        self.legacy_uuid = f"{self.integration_id}-0"


@dataclass
class Output(Device):
    """Output entity in Lutron universe.

    This generally refers to a switched/dimmed load, e.g. light fixture, outlet, etc.
    """

    LIP_MODE: ClassVar[LIPMode] = LIPMode.OUTPUT

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

    def set_level(self, level: float, fade_time: str | None = None) -> LIPCommand:
        """Return a command to set the output level."""
        return self._execute(LIPAction.OUTPUT_LEVEL, value=level, fade_time=fade_time)

    def get_level(self) -> LIPCommand:
        """Return a command to get the output level."""
        return self._query(LIPAction.OUTPUT_LEVEL)

    def start_raising(self) -> LIPCommand:
        """Return a command to start raising the motor."""
        return self._execute(LIPAction.OUTPUT_START_RAISING)

    def start_lowering(self) -> LIPCommand:
        """Return a command to start lowering the motor."""
        return self._execute(LIPAction.OUTPUT_START_LOWERING)

    def stop(self) -> LIPCommand:
        """Return a command to stop the motor."""
        return self._execute(LIPAction.OUTPUT_STOP)

    def jog_raise(self) -> LIPCommand:
        """Return a command to start raising the motor."""
        return self._execute(LIPAction.OUTPUT_MOTOR_JOG_RAISE)

    def jog_lower(self) -> LIPCommand:
        """Return a command to start lowering the motor."""
        return self._execute(LIPAction.OUTPUT_MOTOR_JOG_LOWER)


@dataclass
class KeypadComponent(Device):
    """Base class for keypad components (buttons, LEDs, etc.).

    The integration_id is the keypad ID.
    The lutron component_number is referenced in commands and events.
    This is different from KeypadComponent.number because this property
    is only used for interfacing with the controller.
    """

    LIP_MODE: ClassVar[LIPMode] = LIPMode.DEVICE

    keypad: Any = None
    component_type: str = ""
    component_number: int = 0  # lutron internal number
    number: int = field(init=False, default=0)  # user-friendly number

    def __post_init__(self):
        """Set the legacy UUID and area for keypad components."""
        self.area = self.keypad.area
        self.legacy_uuid = f"{self.integration_id}-{self.component_number}"
        self.number = self.component_number

    @property
    def component_name(self) -> str:
        """The standard component name of the keypad component. E.g., Btn 1, Led 1, CCI 1, etc."""
        return f"{self.component_type} {self.number}"


@dataclass
class Button(KeypadComponent):
    """Object representing a keypad button."""

    engraving: str = ""
    button_type: str = ""
    direction: str = ""
    led_logic: int = 0
    actions: list = field(default_factory=list)

    def __post_init__(self):
        """Set the button name to engraving if available, otherwise use the button number."""
        super().__post_init__()

        self.name = self.engraving
        # Hybrid keypads have dimmer buttons which have no engravings.
        if self.button_type == "SingleSceneRaiseLower":
            self.name = "Dimmer " + self.direction
        # a button without engraving can be a valid button (e.g., keypad lower/raiser buttons)
        if not self.name:
            self.name = f"Unknown Button {self.component_number}"

    @property
    def has_actions(self) -> bool:
        """Return True if the button has actions."""
        return len(self.actions) > 0

    def press(self) -> LIPCommand:
        """Return a command to press the button."""
        return self._execute(LIPAction.DEVICE_PRESS)


@dataclass
class Led(KeypadComponent):
    """Object representing a keypad LED."""

    button: Button | None = field(init=False, default=None)

    def __post_init__(self):
        """Assign the component number."""
        super().__post_init__()

        led_base = 80
        if self.keypad.device_type == "MAIN_REPEATER":
            led_base = 100
        elif self.keypad.device_type == "PHANTOM":
            led_base = 2000
        self.number = self.component_number - led_base

    def turn_on(self) -> LIPCommand:
        """Return a command to turn on the LED."""
        return self._execute(LIPAction.DEVICE_LED_STATE, value=LIPLedState.ON)

    def turn_off(self) -> LIPCommand:
        """Return a command to turn off the LED."""
        return self._execute(LIPAction.DEVICE_LED_STATE, value=LIPLedState.OFF)

    def get_state(self) -> LIPCommand:
        """Return a command to get the LED state."""
        return self._query(LIPAction.DEVICE_LED_STATE)


@dataclass
class Keypad(Device):
    """Object representing a Lutron keypad."""

    LIP_MODE: ClassVar[LIPMode] = LIPMode.DEVICE

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


@dataclass
class MotionSensor(Device):
    """Placeholder class for the motion sensor device.

    Although sensors are represented in the XML, all the protocol
    happens at the OccupancyGroup level. To read the state of an area,
    use area.occupancy_group.

    _CMD_TYPE = 'DEVICE'

    _ACTION_BATTERY_STATUS = 22
    """

    LIP_MODE: ClassVar[LIPMode] = LIPMode.DEVICE


@dataclass
class OccupancyGroup(Device):
    """Represents one or more occupancy/vacancy sensors grouped into an Area."""

    LIP_MODE: ClassVar[LIPMode] = LIPMode.GROUP

    area: Any = None
    group_number: str | None = None

    def bind_area(self, area):
        """Binds the OccupancyGroup to the Area."""
        self.area = area
        self.legacy_uuid = f"{self.area.integration_id}-{self.group_number}"
        self.name = f"Occ {area.name}"
        self.integration_id = area.integration_id

    def get_state(self) -> LIPCommand:
        """Return a command to get the group state."""
        return self._query(LIPAction.GROUP_STATE)


@dataclass
class Sysvar(Device):
    """Represents Lutron variables."""

    LIP_MODE: ClassVar[LIPMode] = LIPMode.SYSVAR

    def set_state(self, value: int) -> LIPCommand:
        """Return a command to set the system variable state."""
        return self._execute(LIPAction.SYSVAR_STATE, value=value)

    def get_state(self) -> LIPCommand:
        """Return a command to get the system variable state."""
        return self._query(LIPAction.SYSVAR_STATE)
