"""Insteon product database."""
import collections

from insteonplm.states.cover import Cover
from insteonplm.states.dimmable import (
    DimmableKeypadA,
    DimmableRemote,
    DimmableSwitch,
    DimmableSwitch_Fan,
)
from insteonplm.states.onOff import (
    OnOffKeypad,
    OnOffKeypadA,
    OnOffSwitch,
    OnOffSwitch_OutletBottom,
    OnOffSwitch_OutletTop,
    OpenClosedRelay,
)
from insteonplm.states.sensor import (
    IoLincSensor,
    LeakSensorDryWet,
    OnOffSensor,
    SmokeCO2Sensor,
    VariableSensor,
)
from insteonplm.states.x10 import (
    X10AllLightsOffSensor,
    X10AllLightsOnSensor,
    X10AllUnitsOffSensor,
    X10DimmableSwitch,
    X10OnOffSensor,
    X10OnOffSwitch,
)

State = collections.namedtuple("Product", "stateType platform")


class IPDB:
    """Embodies the INSTEON Product Database static data and access methods."""

    def __init__(self):
        """Create the INSTEON Product Database (IPDB)."""
        self.states = [
            State(Cover, "cover"),
            State(OnOffSwitch_OutletTop, "switch"),
            State(OnOffSwitch_OutletBottom, "switch"),
            State(OpenClosedRelay, "switch"),
            State(OnOffSwitch, "switch"),
            State(OnOffKeypadA, "switch"),
            State(OnOffKeypad, "switch"),
            State(LeakSensorDryWet, "binary_sensor"),
            State(IoLincSensor, "binary_sensor"),
            State(SmokeCO2Sensor, "sensor"),
            State(OnOffSensor, "binary_sensor"),
            State(VariableSensor, "sensor"),
            State(DimmableSwitch_Fan, "fan"),
            State(DimmableSwitch, "light"),
            State(DimmableRemote, "on_off_events"),
            State(DimmableKeypadA, "light"),
            State(X10DimmableSwitch, "light"),
            State(X10OnOffSwitch, "switch"),
            State(X10OnOffSensor, "binary_sensor"),
            State(X10AllUnitsOffSensor, "binary_sensor"),
            State(X10AllLightsOnSensor, "binary_sensor"),
            State(X10AllLightsOffSensor, "binary_sensor"),
        ]

    def __len__(self):
        """Return the number of INSTEON state types mapped to HA platforms."""
        return len(self.states)

    def __iter__(self):
        """Itterate through the INSTEON state types to HA platforms."""
        yield from self.states

    def __getitem__(self, key):
        """Return a Home Assistant platform from an INSTEON state type."""
        for state in self.states:
            if isinstance(key, state.stateType):
                return state
        return None
