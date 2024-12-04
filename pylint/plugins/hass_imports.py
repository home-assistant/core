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
    "functools": [
        ObsoleteImportMatch(
            reason="replaced by propcache.cached_property",
            constant=re.compile(r"^cached_property$"),
        ),
    ],
    "homeassistant.backports.enum": [
        ObsoleteImportMatch(
            reason="We can now use the Python 3.11 provided enum.StrEnum instead",
            constant=re.compile(r"^StrEnum$"),
        ),
    ],
    "homeassistant.backports.functools": [
        ObsoleteImportMatch(
            reason="replaced by propcache.cached_property",
            constant=re.compile(r"^cached_property$"),
        ),
    ],
    "homeassistant.components.light": [
        ObsoleteImportMatch(
            reason="replaced by ColorMode enum",
            constant=re.compile(r"^COLOR_MODE_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by color modes",
            constant=re.compile("^SUPPORT_(BRIGHTNESS|COLOR_TEMP|COLOR)$"),
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
        ObsoleteImportMatch(
            reason="replaced by MediaClass enum",
            constant=re.compile(r"^MEDIA_CLASS_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by MediaType enum",
            constant=re.compile(r"^MEDIA_TYPE_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by RepeatMode enum",
            constant=re.compile(r"^REPEAT_MODE(\w*)$"),
        ),
    ],
    "homeassistant.components.media_player.const": [
        ObsoleteImportMatch(
            reason="replaced by MediaPlayerEntityFeature enum",
            constant=re.compile(r"^SUPPORT_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by MediaClass enum",
            constant=re.compile(r"^MEDIA_CLASS_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by MediaType enum",
            constant=re.compile(r"^MEDIA_TYPE_(\w*)$"),
        ),
        ObsoleteImportMatch(
            reason="replaced by RepeatMode enum",
            constant=re.compile(r"^REPEAT_MODE(\w*)$"),
        ),
    ],
    "homeassistant.components.vacuum": [
        ObsoleteImportMatch(
            reason="replaced by VacuumEntityFeature enum",
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
            reason="replaced by local constants",
            constant=re.compile(r"^CONF_UNIT_SYSTEM_(\w+)$"),
        ),
    ],
    "homeassistant.helpers.config_validation": [
        ObsoleteImportMatch(
            reason="should be imported from homeassistant/components/<platform>",
            constant=re.compile(r"^PLATFORM_SCHEMA(_BASE)?$"),
        ),
    ],
    "homeassistant.helpers.json": [
        ObsoleteImportMatch(
            reason="moved to homeassistant.util.json",
            constant=re.compile(
                r"^JSON_DECODE_EXCEPTIONS|JSON_ENCODE_EXCEPTIONS|json_loads$"
            ),
        ),
    ],
    "homeassistant.util.unit_system": [
        ObsoleteImportMatch(
            reason="replaced by US_CUSTOMARY_SYSTEM",
            constant=re.compile(r"^IMPERIAL_SYSTEM$"),
        ),
    ],
}

_IGNORE_ROOT_IMPORT = (
    "assist_pipeline",
    "automation",
    "bluetooth",
    "camera",
    "cast",
    "device_automation",
    "device_tracker",
    "ffmpeg",
    "ffmpeg_motion",
    "google_assistant",
    "hardware",
    "homeassistant",
    "homeassistant_hardware",
    "http",
    "manual",
    "plex",
    "recorder",
    "rest",
    "script",
    "sensor",
    "stream",
    "zha",
)


# Blacklist of imports that should be using the namespace
@dataclass
class NamespaceAlias:
    """Class for namespace imports."""

    alias: str
    names: set[str]  # function names


_FORCE_NAMESPACE_IMPORT: dict[str, NamespaceAlias] = {
    "homeassistant.helpers.area_registry": NamespaceAlias("ar", {"async_get"}),
    "homeassistant.helpers.category_registry": NamespaceAlias("cr", {"async_get"}),
    "homeassistant.helpers.device_registry": NamespaceAlias(
        "dr",
        {
            "async_get",
            "async_entries_for_config_entry",
        },
    ),
    "homeassistant.helpers.entity_registry": NamespaceAlias(
        "er",
        {
            "async_get",
            "async_entries_for_config_entry",
        },
    ),
    "homeassistant.helpers.floor_registry": NamespaceAlias("fr", {"async_get"}),
    "homeassistant.helpers.issue_registry": NamespaceAlias("ir", {"async_get"}),
    "homeassistant.helpers.label_registry": NamespaceAlias("lr", {"async_get"}),
}


class HassImportsFormatChecker(BaseChecker):
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
        "W7424": (
            "Import should be using the component root",
            "hass-component-root-import",
            "Used when an import from another component should be "
            "from the component root",
        ),
        "W7425": (
            "`%s` should not be imported directly. Please import `%s` as `%s` "
            "and use `%s.%s`",
            "hass-helper-namespace-import",
            "Used when a helper should be used via the namespace",
        ),
        "W7426": (
            "`%s` should be imported using an alias, such as `%s as %s`",
            "hass-import-constant-alias",
            "Used when a constant should be imported as an alias",
        ),
    }
    options = ()

    def __init__(self, linter: PyLinter) -> None:
        """Initialize the HassImportsFormatChecker."""
        super().__init__(linter)
        self.current_package: str | None = None

    def visit_module(self, node: nodes.Module) -> None:
        """Determine current package."""
        if node.package:
            self.current_package = node.name
        else:
            # Strip name of the current module
            self.current_package = node.name[: node.name.rfind(".")]

    def visit_import(self, node: nodes.Import) -> None:
        """Check for improper `import _` invocations."""
        if self.current_package is None:
            return
        for module, _alias in node.names:
            if module.startswith(f"{self.current_package}."):
                self.add_message("hass-relative-import", node=node)
                continue
            if (
                module.startswith("homeassistant.components.")
                and len(module.split(".")) > 3
            ):
                if (
                    self.current_package.startswith("tests.components.")
                    and self.current_package.split(".")[2] == module.split(".")[2]
                ):
                    # Ignore check if the component being tested matches
                    # the component being imported from
                    continue
                self.add_message("hass-component-root-import", node=node)

    def _visit_importfrom_relative(
        self, current_package: str, node: nodes.ImportFrom
    ) -> None:
        """Check for improper 'from ._ import _' invocations."""
        if (
            node.level <= 1
            or not current_package.startswith("homeassistant.components.")
            and not current_package.startswith("tests.components.")
        ):
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

    def _check_for_constant_alias(
        self,
        node: nodes.ImportFrom,
        current_component: str | None,
        imported_component: str,
    ) -> bool:
        """Check for hass-import-constant-alias."""
        if current_component == imported_component:
            return True

        # Check for `from homeassistant.components.other import DOMAIN`
        for name, alias in node.names:
            if name == "DOMAIN" and (alias is None or alias == "DOMAIN"):
                self.add_message(
                    "hass-import-constant-alias",
                    node=node,
                    args=(
                        "DOMAIN",
                        "DOMAIN",
                        f"{imported_component.upper()}_DOMAIN",
                    ),
                )
                return False

        return True

    def _check_for_component_root_import(
        self,
        node: nodes.ImportFrom,
        current_component: str | None,
        imported_parts: list[str],
        imported_component: str,
    ) -> bool:
        """Check for hass-component-root-import."""
        if (
            current_component == imported_component
            or imported_component in _IGNORE_ROOT_IMPORT
        ):
            return True

        # Check for `from homeassistant.components.other.module import something`
        if len(imported_parts) > 3:
            self.add_message("hass-component-root-import", node=node)
            return False

        # Check for `from homeassistant.components.other import const`
        for name, _ in node.names:
            if name == "const":
                self.add_message("hass-component-root-import", node=node)
                return False

        return True

    def _check_for_relative_import(
        self,
        current_package: str,
        node: nodes.ImportFrom,
        current_component: str | None,
    ) -> bool:
        """Check for hass-relative-import."""
        if node.modname == current_package or node.modname.startswith(
            f"{current_package}."
        ):
            self.add_message("hass-relative-import", node=node)
            return False

        for root in ("homeassistant", "tests"):
            if current_package.startswith(f"{root}.components."):
                if node.modname == f"{root}.components":
                    for name in node.names:
                        if name[0] == current_component:
                            self.add_message("hass-relative-import", node=node)
                            return False
                elif node.modname.startswith(f"{root}.components.{current_component}."):
                    self.add_message("hass-relative-import", node=node)
                    return False

        return True

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Check for improper 'from _ import _' invocations."""
        if not self.current_package:
            return
        if node.level is not None:
            self._visit_importfrom_relative(self.current_package, node)
            return

        # Cache current component
        current_component: str | None = None
        for root in ("homeassistant", "tests"):
            if self.current_package.startswith(f"{root}.components."):
                current_component = self.current_package.split(".")[2]

        # Checks for hass-relative-import
        if not self._check_for_relative_import(
            self.current_package, node, current_component
        ):
            return

        if node.modname.startswith("homeassistant.components."):
            imported_parts = node.modname.split(".")
            imported_component = imported_parts[2]

            # Checks for hass-component-root-import
            if not self._check_for_component_root_import(
                node, current_component, imported_parts, imported_component
            ):
                return

            # Checks for hass-import-constant-alias
            if not self._check_for_constant_alias(
                node, current_component, imported_component
            ):
                return

        # Checks for hass-deprecated-import
        if obsolete_imports := _OBSOLETE_IMPORT.get(node.modname):
            for name_tuple in node.names:
                for obsolete_import in obsolete_imports:
                    if import_match := obsolete_import.constant.match(name_tuple[0]):
                        self.add_message(
                            "hass-deprecated-import",
                            node=node,
                            args=(import_match.string, obsolete_import.reason),
                        )

        # Checks for hass-helper-namespace-import
        if namespace_alias := _FORCE_NAMESPACE_IMPORT.get(node.modname):
            for name in node.names:
                if name[0] in namespace_alias.names:
                    self.add_message(
                        "hass-helper-namespace-import",
                        node=node,
                        args=(
                            name[0],
                            node.modname,
                            namespace_alias.alias,
                            namespace_alias.alias,
                            name[0],
                        ),
                    )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassImportsFormatChecker(linter))
