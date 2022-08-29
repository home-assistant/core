"""Plugin for checking imports."""
from __future__ import annotations

from dataclasses import dataclass
import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


@dataclass
class ObsoleteImportMatch:
    """Class for pattern matching."""

    constant: re.Pattern[str]
    reason: str


_OBSOLETE_IMPORT: dict[str, list[ObsoleteImportMatch]] = {
    "homeassistant.components.alarm_control_panel": [
        ObsoleteImportMatch(
            reason="replaced by AlarmControlPanelEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by CodeFormat enum",
            constant=re.compile(r"^FORMAT_(\w*)$"),
        ),
    ],
    "homeassistant.components.alarm_control_panel.const": [
        ObsoleteImportMatch(
            reason="replaced by AlarmControlPanelEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by CodeFormat enum",
            constant=re.compile(r"^FORMAT_(\w*)$"),
        ),
    ],
    "homeassistant.components.automation": [
        ObsoleteImportMatch(
            reason="replaced by TriggerActionType from helpers.trigger",
            constant=re.compile(r"^AutomationActionType$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by TriggerData from helpers.trigger",
            constant=re.compile(r"^AutomationTriggerData$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by TriggerInfo from helpers.trigger",
            constant=re.compile(r"^AutomationTriggerInfo$"),
        ),
    ],
    "homeassistant.components.binary_sensor": [
        ObsoleteImportMatch(
            reason="replaced by BinarySensorDeviceClass enum",
            constant=re.compile(r"^DEVICE_CLASS_(\w*)$"),
        ),
    ],
    "homeassistant.components.camera": [
        ObsoleteImportMatch(
            reason="replaced by CameraEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by StreamType enum",
            constant=re.compile(r"^STREAM_TYPE_(\w*)$"),
        ),
    ],
    "homeassistant.components.camera.const": [
        ObsoleteImportMatch(
            reason="replaced by StreamType enum",
            constant=re.compile(r"^STREAM_TYPE_(\w*)$"),
        ),
    ],
    "homeassistant.components.climate": [
        ObsoleteImportMatch(
            reason="replaced by HVACMode enum",
            constant=re.compile(r"^HVAC_MODE_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by ClimateEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.climate.const": [
        ObsoleteImportMatch(
            reason="replaced by HVACAction enum",
            constant=re.compile(r"^CURRENT_HVAC_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by HVACMode enum",
            constant=re.compile(r"^HVAC_MODE_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by ClimateEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.cover": [
        ObsoleteImportMatch(
            reason="replaced by CoverDeviceClass enum",
            constant=re.compile(r"^DEVICE_CLASS_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by CoverEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.device_tracker": [
        ObsoleteImportMatch(
            reason="replaced by SourceType enum",
            constant=re.compile(r"^SOURCE_TYPE_\w+$"),
        ),
    ],
    "homeassistant.components.device_tracker.const": [
        ObsoleteImportMatch(
            reason="replaced by SourceType enum",
            constant=re.compile(r"^SOURCE_TYPE_\w+$"),
        ),
    ],
    "homeassistant.components.fan": [
        ObsoleteImportMatch(
            reason="replaced by FanEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.humidifier": [
        ObsoleteImportMatch(
            reason="replaced by HumidifierDeviceClass enum",
            constant=re.compile(r"^DEVICE_CLASS_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by HumidifierEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.humidifier.const": [
        ObsoleteImportMatch(
            reason="replaced by HumidifierDeviceClass enum",
            constant=re.compile(r"^DEVICE_CLASS_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by HumidifierEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.lock": [
        ObsoleteImportMatch(
            reason="replaced by LockEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.light": [
        ObsoleteImportMatch(
            reason="replaced by ColorMode enum",
            constant=re.compile(r"^COLOR_MODE_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by LightEntityFeature enum",
            constant=re.compile("^SUPPORT_(EFFECT|FLASH|TRANSITION)$"),
        ),
    ],
    "homeassistant.components.media_player": [
        ObsoleteImportMatch(
            reason="replaced by MediaPlayerDeviceClass enum",
            constant=re.compile(r"^DEVICE_CLASS_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by MediaPlayerEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.media_player.const": [
        ObsoleteImportMatch(
            reason="replaced by MediaPlayerEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.remote": [
        ObsoleteImportMatch(
            reason="replaced by RemoteEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.sensor": [
        ObsoleteImportMatch(
            reason="replaced by SensorDeviceClass enum",
            constant=re.compile(r"^DEVICE_CLASS_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by SensorStateClass enum",
            constant=re.compile(r"^STATE_CLASS_(\w*)$"),
        ),
    ],
    "homeassistant.components.siren": [
        ObsoleteImportMatch(
            reason="replaced by SirenEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.siren.const": [
        ObsoleteImportMatch(
            reason="replaced by SirenEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.switch": [
        ObsoleteImportMatch(
            reason="replaced by SwitchDeviceClass enum",
            constant=re.compile(r"^DEVICE_CLASS_(\w*)$"),
        ),
    ],
    "homeassistant.components.vacuum": [
        ObsoleteImportMatch(
            reason="replaced by VacuumEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.components.water_heater": [
        ObsoleteImportMatch(
            reason="replaced by WaterHeaterEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
    ],
    "homeassistant.config_entries": [
        ObsoleteImportMatch(
            reason="replaced by ConfigEntryDisabler enum",
            constant=re.compile(r"^DISABLED_(\w*)$"),
        ),
    ],
    "homeassistant.const": [
        ObsoleteImportMatch(
            reason="replaced by SensorDeviceClass enum",
            constant=re.compile(r"^DEVICE_CLASS_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by EntityCategory enum",
            constant=re.compile(r"^(ENTITY_CATEGORY_(\w*))|(ENTITY_CATEGORIES)$"),
        ),
    ],
    "homeassistant.core": [
        ObsoleteImportMatch(
            reason="replaced by ConfigSource enum",
            constant=re.compile(r"^SOURCE_(\w*)$"),
        ),
    ],
    "homeassistant.data_entry_flow": [
        ObsoleteImportMatch(
            reason="replaced by FlowResultType enum",
            constant=re.compile(r"^RESULT_TYPE_(\w*)$"),
        ),
    ],
    "homeassistant.helpers.device_registry": [
        ObsoleteImportMatch(
            reason="replaced by DeviceEntryDisabler enum",
            constant=re.compile(r"^DISABLED_(\w*)$"),
        ),
    ],
}


class HassImportsFormatChecker(BaseChecker):  # type: ignore[misc]
    """Checker for imports."""

    name = "hass_imports"
    priority = -1
    msgs = {
        "W7421": (
            "Relative import should be used",
            "hass-relative-import",
            "Used when absolute import should be replaced with relative import",
        ),
        "W7422": (
            "%s is deprecated, %s",
            "hass-deprecated-import",
            "Used when import is deprecated",
        ),
        "W7423": (
            "Absolute import should be used",
            "hass-absolute-import",
            "Used when relative import should be replaced with absolute import",
        ),
    }
    options = ()

    def __init__(self, linter: PyLinter | None = None) -> None:
        super().__init__(linter)
        self.current_package: str | None = None

    def visit_module(self, node: nodes.Module) -> None:
        """Called when a Module node is visited."""
        if node.package:
            self.current_package = node.name
        else:
            # Strip name of the current module
            self.current_package = node.name[: node.name.rfind(".")]

    def visit_import(self, node: nodes.Import) -> None:
        """Called when a Import node is visited."""
        for module, _alias in node.names:
            if module.startswith(f"{self.current_package}."):
                self.add_message("hass-relative-import", node=node)

    def _visit_importfrom_relative(self, current_package: str, node: nodes.ImportFrom) -> None:
        """Called when a ImportFrom node is visited."""
        if node.level <= 1 or not current_package.startswith("homeassistant.components"):
            return
        split_package = current_package.split(".")
        if not node.modname and len(split_package) == node.level + 1:
            for name in node.names:
                # Allow relative import to component root
                if name[0] != split_package[2]:
                    self.add_message("hass-absolute-import", node=node)
                    return
            return
        if len(split_package) < node.level + 2:
            self.add_message("hass-absolute-import", node=node)

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Called when a ImportFrom node is visited."""
        if not self.current_package:
            return
        if node.level is not None:
            self._visit_importfrom_relative(self.current_package, node)
            return
        if node.modname == self.current_package or node.modname.startswith(
            f"{self.current_package}."
        ):
            self.add_message("hass-relative-import", node=node)
            return
        if self.current_package.startswith("homeassistant.components") and node.modname == "homeassistant.components":
            for name in node.names:
                if name[0] == self.current_package.split(".")[2]:
                    self.add_message("hass-relative-import", node=node)
            return
        if obsolete_imports := _OBSOLETE_IMPORT.get(node.modname):
            for name_tuple in node.names:
                for obsolete_import in obsolete_imports:
                    if import_match := obsolete_import.constant.match(name_tuple[0]):
                        self.add_message(
                            "hass-deprecated-import",
                            node=node,
                            args=(import_match.string, obsolete_import.reason),
                        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassImportsFormatChecker(linter))
