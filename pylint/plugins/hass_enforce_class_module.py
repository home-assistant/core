"""Plugin for checking if class is in correct module."""

from __future__ import annotations

from ast import ClassDef
from dataclasses import dataclass

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


@dataclass
class ClassModuleMatch:
    """Class for pattern matching."""

    expected_module: str
    base_class: str


_MODULES = [
    ClassModuleMatch("alarm_control_panel", "AlarmControlPanelEntityDescription"),
    ClassModuleMatch("assist_satellite", "AssistSatelliteEntityDescription"),
    ClassModuleMatch("binary_sensor", "BinarySensorEntityDescription"),
    ClassModuleMatch("button", "ButtonEntityDescription"),
    ClassModuleMatch("camera", "CameraEntityDescription"),
    ClassModuleMatch("climate", "ClimateEntityDescription"),
    ClassModuleMatch("coordinator", "DataUpdateCoordinator"),
    ClassModuleMatch("cover", "CoverEntityDescription"),
    ClassModuleMatch("date", "DateEntityDescription"),
    ClassModuleMatch("datetime", "DateTimeEntityDescription"),
    ClassModuleMatch("event", "EventEntityDescription"),
    ClassModuleMatch("image", "ImageEntityDescription"),
    ClassModuleMatch("image_processing", "ImageProcessingEntityDescription"),
    ClassModuleMatch("lawn_mower", "LawnMowerEntityDescription"),
    ClassModuleMatch("lock", "LockEntityDescription"),
    ClassModuleMatch("media_player", "MediaPlayerEntityDescription"),
    ClassModuleMatch("notify", "NotifyEntityDescription"),
    ClassModuleMatch("number", "NumberEntityDescription"),
    ClassModuleMatch("select", "SelectEntityDescription"),
    ClassModuleMatch("sensor", "SensorEntityDescription"),
    ClassModuleMatch("text", "TextEntityDescription"),
    ClassModuleMatch("time", "TimeEntityDescription"),
    ClassModuleMatch("update", "UpdateEntityDescription"),
    ClassModuleMatch("vacuum", "VacuumEntityDescription"),
    ClassModuleMatch("water_heater", "WaterHeaterEntityDescription"),
    ClassModuleMatch("weather", "WeatherEntityDescription"),
]


class HassEnforceClassModule(BaseChecker):
    """Checker for class in correct module."""

    name = "hass_enforce_class_module"
    priority = -1
    msgs = {
        "C7461": (
            "Derived %s is recommended to be placed in the '%s' module",
            "hass-enforce-class-module",
            "Used when derived class should be placed in its own module.",
        ),
    }

    def visit_classdef(self, node: nodes.ClassDef) -> None:
        """Check if derived class is placed in its own module."""
        root_name = node.root().name

        # we only want to check components
        if not root_name.startswith("homeassistant.components."):
            return
        parts = root_name.split(".")
        current_module = parts[3] if len(parts) > 3 else ""

        ancestors: list[ClassDef] | None = None

        for match in _MODULES:
            # Allow module.py and module/sub_module.py
            if current_module == match.expected_module:
                continue

            if ancestors is None:
                ancestors = list(node.ancestors())  # cache result for other modules

            for ancestor in ancestors:
                if ancestor.name == match.base_class:
                    self.add_message(
                        "hass-enforce-class-module",
                        node=node,
                        args=(match.base_class, match.expected_module),
                    )
                    return


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceClassModule(linter))
