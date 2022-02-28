"""Generate mypy config."""
from __future__ import annotations

import configparser
import io
import os
from pathlib import Path
from typing import Final

from homeassistant.const import REQUIRED_PYTHON_VER

from .model import Config, Integration

# Modules which have type hints which known to be broken.
# If you are an author of component listed here, please fix these errors and
# remove your component from this list to enable type checks.
# Do your best to not add anything new here.
IGNORED_MODULES: Final[list[str]] = [
    "homeassistant.components.blueprint.importer",
    "homeassistant.components.blueprint.models",
    "homeassistant.components.blueprint.websocket_api",
    "homeassistant.components.cloud.client",
    "homeassistant.components.cloud.http_api",
    "homeassistant.components.conversation",
    "homeassistant.components.conversation.default_agent",
    "homeassistant.components.deconz.alarm_control_panel",
    "homeassistant.components.deconz.binary_sensor",
    "homeassistant.components.deconz.climate",
    "homeassistant.components.deconz.cover",
    "homeassistant.components.deconz.fan",
    "homeassistant.components.deconz.light",
    "homeassistant.components.deconz.lock",
    "homeassistant.components.deconz.logbook",
    "homeassistant.components.deconz.number",
    "homeassistant.components.deconz.sensor",
    "homeassistant.components.deconz.siren",
    "homeassistant.components.deconz.switch",
    "homeassistant.components.denonavr.config_flow",
    "homeassistant.components.denonavr.media_player",
    "homeassistant.components.denonavr.receiver",
    "homeassistant.components.evohome",
    "homeassistant.components.evohome.climate",
    "homeassistant.components.evohome.water_heater",
    "homeassistant.components.google_assistant.helpers",
    "homeassistant.components.google_assistant.http",
    "homeassistant.components.google_assistant.report_state",
    "homeassistant.components.google_assistant.trait",
    "homeassistant.components.gree.climate",
    "homeassistant.components.gree.switch",
    "homeassistant.components.harmony",
    "homeassistant.components.harmony.config_flow",
    "homeassistant.components.harmony.data",
    "homeassistant.components.hassio",
    "homeassistant.components.hassio.auth",
    "homeassistant.components.hassio.binary_sensor",
    "homeassistant.components.hassio.ingress",
    "homeassistant.components.hassio.sensor",
    "homeassistant.components.hassio.system_health",
    "homeassistant.components.hassio.websocket_api",
    "homeassistant.components.here_travel_time.sensor",
    "homeassistant.components.home_plus_control",
    "homeassistant.components.home_plus_control.api",
    "homeassistant.components.homekit.aidmanager",
    "homeassistant.components.homekit.config_flow",
    "homeassistant.components.homekit.util",
    "homeassistant.components.honeywell.climate",
    "homeassistant.components.icloud",
    "homeassistant.components.icloud.account",
    "homeassistant.components.icloud.device_tracker",
    "homeassistant.components.icloud.sensor",
    "homeassistant.components.influxdb",
    "homeassistant.components.input_datetime",
    "homeassistant.components.izone.climate",
    "homeassistant.components.konnected",
    "homeassistant.components.konnected.config_flow",
    "homeassistant.components.kostal_plenticore.helper",
    "homeassistant.components.kostal_plenticore.select",
    "homeassistant.components.kostal_plenticore.sensor",
    "homeassistant.components.kostal_plenticore.switch",
    "homeassistant.components.lovelace",
    "homeassistant.components.lovelace.dashboard",
    "homeassistant.components.lovelace.resources",
    "homeassistant.components.lovelace.websocket",
    "homeassistant.components.lutron_caseta",
    "homeassistant.components.lutron_caseta.device_trigger",
    "homeassistant.components.lutron_caseta.switch",
    "homeassistant.components.lyric.climate",
    "homeassistant.components.lyric.config_flow",
    "homeassistant.components.lyric.sensor",
    "homeassistant.components.melcloud",
    "homeassistant.components.melcloud.climate",
    "homeassistant.components.meteo_france.sensor",
    "homeassistant.components.meteo_france.weather",
    "homeassistant.components.minecraft_server",
    "homeassistant.components.minecraft_server.helpers",
    "homeassistant.components.minecraft_server.sensor",
    "homeassistant.components.nilu.air_quality",
    "homeassistant.components.nzbget",
    "homeassistant.components.nzbget.config_flow",
    "homeassistant.components.nzbget.coordinator",
    "homeassistant.components.nzbget.switch",
    "homeassistant.components.omnilogic.common",
    "homeassistant.components.omnilogic.sensor",
    "homeassistant.components.omnilogic.switch",
    "homeassistant.components.onvif.base",
    "homeassistant.components.onvif.binary_sensor",
    "homeassistant.components.onvif.button",
    "homeassistant.components.onvif.camera",
    "homeassistant.components.onvif.config_flow",
    "homeassistant.components.onvif.device",
    "homeassistant.components.onvif.event",
    "homeassistant.components.onvif.models",
    "homeassistant.components.onvif.parsers",
    "homeassistant.components.onvif.sensor",
    "homeassistant.components.ozw",
    "homeassistant.components.ozw.climate",
    "homeassistant.components.ozw.entity",
    "homeassistant.components.philips_js",
    "homeassistant.components.philips_js.config_flow",
    "homeassistant.components.philips_js.device_trigger",
    "homeassistant.components.philips_js.light",
    "homeassistant.components.philips_js.media_player",
    "homeassistant.components.plex.media_player",
    "homeassistant.components.profiler",
    "homeassistant.components.solaredge.config_flow",
    "homeassistant.components.solaredge.coordinator",
    "homeassistant.components.solaredge.sensor",
    "homeassistant.components.sonos",
    "homeassistant.components.sonos.alarms",
    "homeassistant.components.sonos.binary_sensor",
    "homeassistant.components.sonos.diagnostics",
    "homeassistant.components.sonos.entity",
    "homeassistant.components.sonos.favorites",
    "homeassistant.components.sonos.helpers",
    "homeassistant.components.sonos.media_browser",
    "homeassistant.components.sonos.media_player",
    "homeassistant.components.sonos.number",
    "homeassistant.components.sonos.sensor",
    "homeassistant.components.sonos.speaker",
    "homeassistant.components.sonos.statistics",
    "homeassistant.components.system_health",
    "homeassistant.components.telegram_bot.polling",
    "homeassistant.components.template.number",
    "homeassistant.components.template.sensor",
    "homeassistant.components.toon",
    "homeassistant.components.toon.config_flow",
    "homeassistant.components.toon.models",
    "homeassistant.components.unifi",
    "homeassistant.components.unifi.config_flow",
    "homeassistant.components.unifi.device_tracker",
    "homeassistant.components.unifi.diagnostics",
    "homeassistant.components.unifi.unifi_entity_base",
    "homeassistant.components.upnp",
    "homeassistant.components.upnp.binary_sensor",
    "homeassistant.components.upnp.config_flow",
    "homeassistant.components.upnp.device",
    "homeassistant.components.upnp.sensor",
    "homeassistant.components.vizio.config_flow",
    "homeassistant.components.vizio.media_player",
    "homeassistant.components.withings",
    "homeassistant.components.withings.binary_sensor",
    "homeassistant.components.withings.common",
    "homeassistant.components.withings.config_flow",
    "homeassistant.components.xbox",
    "homeassistant.components.xbox.base_sensor",
    "homeassistant.components.xbox.binary_sensor",
    "homeassistant.components.xbox.browse_media",
    "homeassistant.components.xbox.media_source",
    "homeassistant.components.xbox.sensor",
    "homeassistant.components.xiaomi_aqara",
    "homeassistant.components.xiaomi_aqara.binary_sensor",
    "homeassistant.components.xiaomi_aqara.lock",
    "homeassistant.components.xiaomi_aqara.sensor",
    "homeassistant.components.xiaomi_miio",
    "homeassistant.components.xiaomi_miio.air_quality",
    "homeassistant.components.xiaomi_miio.binary_sensor",
    "homeassistant.components.xiaomi_miio.device",
    "homeassistant.components.xiaomi_miio.device_tracker",
    "homeassistant.components.xiaomi_miio.fan",
    "homeassistant.components.xiaomi_miio.humidifier",
    "homeassistant.components.xiaomi_miio.light",
    "homeassistant.components.xiaomi_miio.sensor",
    "homeassistant.components.xiaomi_miio.switch",
    "homeassistant.components.yeelight",
    "homeassistant.components.yeelight.light",
    "homeassistant.components.yeelight.scanner",
    "homeassistant.components.zha.alarm_control_panel",
    "homeassistant.components.zha.api",
    "homeassistant.components.zha.binary_sensor",
    "homeassistant.components.zha.button",
    "homeassistant.components.zha.climate",
    "homeassistant.components.zha.config_flow",
    "homeassistant.components.zha.core.channels",
    "homeassistant.components.zha.core.channels.base",
    "homeassistant.components.zha.core.channels.closures",
    "homeassistant.components.zha.core.channels.general",
    "homeassistant.components.zha.core.channels.homeautomation",
    "homeassistant.components.zha.core.channels.hvac",
    "homeassistant.components.zha.core.channels.lighting",
    "homeassistant.components.zha.core.channels.lightlink",
    "homeassistant.components.zha.core.channels.manufacturerspecific",
    "homeassistant.components.zha.core.channels.measurement",
    "homeassistant.components.zha.core.channels.protocol",
    "homeassistant.components.zha.core.channels.security",
    "homeassistant.components.zha.core.channels.smartenergy",
    "homeassistant.components.zha.core.decorators",
    "homeassistant.components.zha.core.device",
    "homeassistant.components.zha.core.discovery",
    "homeassistant.components.zha.core.gateway",
    "homeassistant.components.zha.core.group",
    "homeassistant.components.zha.core.helpers",
    "homeassistant.components.zha.core.registries",
    "homeassistant.components.zha.core.store",
    "homeassistant.components.zha.core.typing",
    "homeassistant.components.zha.cover",
    "homeassistant.components.zha.device_action",
    "homeassistant.components.zha.device_tracker",
    "homeassistant.components.zha.entity",
    "homeassistant.components.zha.fan",
    "homeassistant.components.zha.light",
    "homeassistant.components.zha.lock",
    "homeassistant.components.zha.select",
    "homeassistant.components.zha.sensor",
    "homeassistant.components.zha.siren",
    "homeassistant.components.zha.switch",
    "homeassistant.components.zwave",
    "homeassistant.components.zwave.migration",
    "homeassistant.components.zwave.node_entity",
]

# Component modules which should set no_implicit_reexport = true.
NO_IMPLICIT_REEXPORT_MODULES: set[str] = {
    "homeassistant.components",
    "homeassistant.components.diagnostics.*",
}

HEADER: Final = """
# Automatically generated by hassfest.
#
# To update, run python3 -m script.hassfest -p mypy_config

""".lstrip()

GENERAL_SETTINGS: Final[dict[str, str]] = {
    "python_version": ".".join(str(x) for x in REQUIRED_PYTHON_VER[:2]),
    "show_error_codes": "true",
    "follow_imports": "silent",
    # Enable some checks globally.
    "ignore_missing_imports": "true",
    "strict_equality": "true",
    "warn_incomplete_stub": "true",
    "warn_redundant_casts": "true",
    "warn_unused_configs": "true",
    "warn_unused_ignores": "true",
}

# This is basically the list of checks which is enabled for "strict=true".
# "strict=false" in config files does not turn strict settings off if they've been
# set in a more general section (it instead means as if strict was not specified at
# all), so we need to list all checks manually to be able to flip them wholesale.
STRICT_SETTINGS: Final[list[str]] = [
    "check_untyped_defs",
    "disallow_incomplete_defs",
    "disallow_subclassing_any",
    "disallow_untyped_calls",
    "disallow_untyped_decorators",
    "disallow_untyped_defs",
    "no_implicit_optional",
    "warn_return_any",
    "warn_unreachable",
    # TODO: turn these on, address issues
    # "disallow_any_generics",
    # "no_implicit_reexport",
]

# Strict settings are already applied for core files.
# To enable granular typing, add additional settings if core files are given.
STRICT_SETTINGS_CORE: Final[list[str]] = [
    "disallow_any_generics",
]


def _strict_module_in_ignore_list(
    module: str, ignored_modules_set: set[str]
) -> str | None:
    if module in ignored_modules_set:
        return module
    if module.endswith("*"):
        module = module[:-1]
        for ignored_module in ignored_modules_set:
            if ignored_module.startswith(module):
                return ignored_module
    return None


def generate_and_validate(config: Config) -> str:
    """Validate and generate mypy config."""

    config_path = config.root / ".strict-typing"

    with config_path.open() as fp:
        lines = fp.readlines()

    # Filter empty and commented lines.
    parsed_modules: list[str] = [
        line.strip()
        for line in lines
        if line.strip() != "" and not line.startswith("#")
    ]

    strict_modules: list[str] = []
    strict_core_modules: list[str] = []
    for module in parsed_modules:
        if module.startswith("homeassistant.components"):
            strict_modules.append(module)
        else:
            strict_core_modules.append(module)

    ignored_modules_set: set[str] = set(IGNORED_MODULES)
    for module in strict_modules:
        if (
            not module.startswith("homeassistant.components.")
            and module != "homeassistant.components"
        ):
            config.add_error(
                "mypy_config", f"Only components should be added: {module}"
            )
        if ignored_module := _strict_module_in_ignore_list(module, ignored_modules_set):
            config.add_error(
                "mypy_config",
                f"Module '{ignored_module}' is in ignored list in mypy_config.py",
            )

    # Validate that all modules exist.
    all_modules = (
        strict_modules
        + strict_core_modules
        + IGNORED_MODULES
        + list(NO_IMPLICIT_REEXPORT_MODULES)
    )
    for module in all_modules:
        if module.endswith(".*"):
            module_path = Path(module[:-2].replace(".", os.path.sep))
            if not module_path.is_dir():
                config.add_error("mypy_config", f"Module '{module} is not a folder")
        else:
            module = module.replace(".", os.path.sep)
            module_path = Path(f"{module}.py")
            if module_path.is_file():
                continue
            module_path = Path(module) / "__init__.py"
            if not module_path.is_file():
                config.add_error("mypy_config", f"Module '{module} doesn't exist")

    # Don't generate mypy.ini if there're errors found because it will likely crash.
    if any(err.plugin == "mypy_config" for err in config.errors):
        return ""

    mypy_config = configparser.ConfigParser()

    general_section = "mypy"
    mypy_config.add_section(general_section)
    for key, value in GENERAL_SETTINGS.items():
        mypy_config.set(general_section, key, value)
    for key in STRICT_SETTINGS:
        mypy_config.set(general_section, key, "true")

    # By default enable no_implicit_reexport only for homeassistant.*
    # Disable it afterwards for all components
    components_section = "mypy-homeassistant.*"
    mypy_config.add_section(components_section)
    mypy_config.set(components_section, "no_implicit_reexport", "true")

    for core_module in strict_core_modules:
        core_section = f"mypy-{core_module}"
        mypy_config.add_section(core_section)
        for key in STRICT_SETTINGS_CORE:
            mypy_config.set(core_section, key, "true")

    # By default strict checks are disabled for components.
    components_section = "mypy-homeassistant.components.*"
    mypy_config.add_section(components_section)
    for key in STRICT_SETTINGS:
        mypy_config.set(components_section, key, "false")
    mypy_config.set(components_section, "no_implicit_reexport", "false")

    for strict_module in strict_modules:
        strict_section = f"mypy-{strict_module}"
        mypy_config.add_section(strict_section)
        for key in STRICT_SETTINGS:
            mypy_config.set(strict_section, key, "true")
        if strict_module in NO_IMPLICIT_REEXPORT_MODULES:
            mypy_config.set(strict_section, "no_implicit_reexport", "true")

    for reexport_module in NO_IMPLICIT_REEXPORT_MODULES.difference(strict_modules):
        reexport_section = f"mypy-{reexport_module}"
        mypy_config.add_section(reexport_section)
        mypy_config.set(reexport_section, "no_implicit_reexport", "true")

    # Disable strict checks for tests
    tests_section = "mypy-tests.*"
    mypy_config.add_section(tests_section)
    for key in STRICT_SETTINGS:
        mypy_config.set(tests_section, key, "false")

    for ignored_module in IGNORED_MODULES:
        ignored_section = f"mypy-{ignored_module}"
        mypy_config.add_section(ignored_section)
        mypy_config.set(ignored_section, "ignore_errors", "true")

    with io.StringIO() as fp:
        mypy_config.write(fp)
        fp.seek(0)
        return HEADER + fp.read().strip()


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate mypy config."""
    config_path = config.root / "mypy.ini"
    config.cache["mypy_config"] = content = generate_and_validate(config)

    if any(err.plugin == "mypy_config" for err in config.errors):
        return

    with open(str(config_path)) as fp:
        if fp.read().strip() != content:
            config.add_error(
                "mypy_config",
                "File mypy.ini is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate mypy config."""
    config_path = config.root / "mypy.ini"
    with open(str(config_path), "w") as fp:
        fp.write(f"{config.cache['mypy_config']}\n")
