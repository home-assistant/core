"""Representation of ISYEntity Types."""

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import Dict


class ISYEntity(Entity):
    """Representation of an ISY994 device."""

    _attrs = {}
    _name: str = None

    def __init__(self, node) -> None:
        """Initialize the insteon device."""
        self._node = node
        self._change_handler = None
        self._control_handler = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.status.subscribe("changed", self.on_update)

        if hasattr(self._node, "controlEvents"):
            self._control_handler = self._node.controlEvents.subscribe(self.on_control)

    def on_update(self, event: object) -> None:
        """Handle the update event from the ISY994 Node."""
        self.schedule_update_ha_state()

    def on_control(self, event: object) -> None:
        """Handle a control event from the ISY994 Node."""
        self.hass.bus.fire(
            "isy994_control", {"entity_id": self.entity_id, "control": event}
        )

    @property
    def unique_id(self) -> str:
        """Get the unique identifier of the device."""
        # pylint: disable=protected-access
        if hasattr(self._node, "_id"):
            return self._node._id

        return None

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._name or str(self._node.name)

    @property
    def should_poll(self) -> bool:
        """No polling required since we're using the subscription."""
        return False

    @property
    def value(self) -> int:
        """Get the current value of the device."""
        # pylint: disable=protected-access
        return self._node.status._val

    def is_unknown(self) -> bool:
        """Get whether or not the value of this Entity's node is unknown.

        PyISY reports unknown values as -inf
        """
        return self.value == -1 * float("inf")

    @property
    def state(self):
        """Return the state of the ISY device."""
        if self.is_unknown():
            return None
        return super().state


class ISYNodeEntity(ISYEntity):
    """Representation of a ISY Nodebase (Node/Group) entity."""

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        attr = {}
        if hasattr(self._node, "aux_properties"):
            for name, val in self._node.aux_properties.items():
                attr[name] = f"{val.get('value')} {val.get('uom')}"
        return attr


class ISYProgramEntity(ISYEntity):
    """Representation of an ISY994 program base."""

    def __init__(self, name: str, status, actions=None) -> None:
        """Initialize the ISY994 program-based entity."""
        super().__init__(status)
        self._name = name
        self._actions = actions
