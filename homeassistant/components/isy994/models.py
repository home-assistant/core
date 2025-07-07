"""The ISY/IoX integration data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pyisy import ISY
from pyisy.constants import PROTO_INSTEON
from pyisy.networking import NetworkCommand
from pyisy.nodes import Group, Node
from pyisy.programs import Program
from pyisy.variables import Variable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_NETWORK,
    NODE_AUX_PROP_PLATFORMS,
    NODE_PLATFORMS,
    PROGRAM_PLATFORMS,
    ROOT_NODE_PLATFORMS,
    VARIABLE_PLATFORMS,
)

type IsyConfigEntry = ConfigEntry[IsyData]


@dataclass
class IsyData:
    """Data for the ISY/IoX integration."""

    root: ISY
    nodes: dict[Platform, list[Node | Group]]
    root_nodes: dict[Platform, list[Node]]
    variables: dict[Platform, list[Variable]]
    programs: dict[Platform, list[tuple[str, Program, Program]]]
    net_resources: list[NetworkCommand]
    devices: dict[str, DeviceInfo]
    aux_properties: dict[Platform, list[tuple[Node, str]]]

    def __init__(self) -> None:
        """Initialize an empty ISY data class."""
        self.nodes = {p: [] for p in NODE_PLATFORMS}
        self.root_nodes = {p: [] for p in ROOT_NODE_PLATFORMS}
        self.aux_properties = {p: [] for p in NODE_AUX_PROP_PLATFORMS}
        self.programs = {p: [] for p in PROGRAM_PLATFORMS}
        self.variables = {p: [] for p in VARIABLE_PLATFORMS}
        self.net_resources = []
        self.devices = {}

    @property
    def uuid(self) -> str:
        """Return the ISY UUID identification."""
        return cast(str, self.root.uuid)

    def uid_base(self, node: Node | Group | Variable | Program | NetworkCommand) -> str:
        """Return the unique id base string for a given node."""
        if isinstance(node, NetworkCommand):
            return f"{self.uuid}_{CONF_NETWORK}_{node.address}"
        return f"{self.uuid}_{node.address}"

    @property
    def unique_ids(self) -> set[tuple[Platform, str]]:
        """Return all the unique ids for a config entry id."""
        current_unique_ids: set[tuple[Platform, str]] = {
            (Platform.BUTTON, f"{self.uuid}_query")
        }

        # Structure and prefixes here must match what's added in __init__ and helpers
        for platform in NODE_PLATFORMS:
            for node in self.nodes[platform]:
                current_unique_ids.add((platform, self.uid_base(node)))

        for platform in NODE_AUX_PROP_PLATFORMS:
            for node, control in self.aux_properties[platform]:
                current_unique_ids.add((platform, f"{self.uid_base(node)}_{control}"))

        for platform in PROGRAM_PLATFORMS:
            for _, node, _ in self.programs[platform]:
                current_unique_ids.add((platform, self.uid_base(node)))

        for platform in VARIABLE_PLATFORMS:
            for node in self.variables[platform]:
                current_unique_ids.add((platform, self.uid_base(node)))
                if platform == Platform.NUMBER:
                    current_unique_ids.add((platform, f"{self.uid_base(node)}_init"))

        for platform in ROOT_NODE_PLATFORMS:
            for node in self.root_nodes[platform]:
                current_unique_ids.add((platform, f"{self.uid_base(node)}_query"))
                if platform == Platform.BUTTON and node.protocol == PROTO_INSTEON:
                    current_unique_ids.add((platform, f"{self.uid_base(node)}_beep"))

        for node in self.net_resources:
            current_unique_ids.add((Platform.BUTTON, self.uid_base(node)))

        return current_unique_ids
