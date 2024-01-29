"""Script to check the configuration file."""
from __future__ import annotations

import argparse
import asyncio
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from glob import glob
import logging
import os
from typing import Any
from unittest.mock import patch

from homeassistant import core, loader
from homeassistant.config import get_default_config_dir
from homeassistant.config_entries import ConfigEntries
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.check_config import async_check_ha_config_file
from homeassistant.util.yaml import Secrets
import homeassistant.util.yaml.loader as yaml_loader

# mypy: allow-untyped-calls, allow-untyped-defs

REQUIREMENTS = ("colorlog==6.8.2",)

_LOGGER = logging.getLogger(__name__)
MOCKS: dict[str, tuple[str, Callable]] = {
    "load": ("homeassistant.util.yaml.loader.load_yaml", yaml_loader.load_yaml),
    "load*": ("homeassistant.config.load_yaml_dict", yaml_loader.load_yaml_dict),
    "secrets": ("homeassistant.util.yaml.loader.secret_yaml", yaml_loader.secret_yaml),
}

PATCHES: dict[str, Any] = {}

C_HEAD = "bold"
ERROR_STR = "General Errors"
WARNING_STR = "General Warnings"


def color(the_color, *args, reset=None):
    """Color helper."""
    # pylint: disable-next=import-outside-toplevel
    from colorlog.escape_codes import escape_codes, parse_colors

    try:
        if not args:
            assert reset is None, "You cannot reset if nothing being printed"
            return parse_colors(the_color)
        return parse_colors(the_color) + " ".join(args) + escape_codes[reset or "reset"]
    except KeyError as k:
        raise ValueError(f"Invalid color {k!s} in {the_color}") from k


def run(script_args: list) -> int:
    """Handle check config commandline script."""
    parser = argparse.ArgumentParser(description="Check Home Assistant configuration.")
    parser.add_argument("--script", choices=["check_config"])
    parser.add_argument(
        "-c",
        "--config",
        default=get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration",
    )
    parser.add_argument(
        "-i",
        "--info",
        nargs="?",
        default=None,
        const="all",
        help="Show a portion of the config",
    )
    parser.add_argument(
        "-f", "--files", action="store_true", help="Show used configuration files"
    )
    parser.add_argument(
        "-s", "--secrets", action="store_true", help="Show secret information"
    )

    args, unknown = parser.parse_known_args()
    if unknown:
        print(color("red", "Unknown arguments:", ", ".join(unknown)))

    config_dir = os.path.join(os.getcwd(), args.config)

    print(color("bold", "Testing configuration at", config_dir))

    res = check(config_dir, args.secrets)

    domain_info: list[str] = []
    if args.info:
        domain_info = args.info.split(",")

    if args.files:
        print(color(C_HEAD, "yaml files"), "(used /", color("red", "not used") + ")")
        deps = os.path.join(config_dir, "deps")
        yaml_files = [
            f
            for f in glob(os.path.join(config_dir, "**/*.yaml"), recursive=True)
            if not f.startswith(deps)
        ]

        for yfn in sorted(yaml_files):
            the_color = "" if yfn in res["yaml_files"] else "red"
            print(color(the_color, "-", yfn))

    if res["except"]:
        print(color("bold_white", "Failed config"))
        for domain, config in res["except"].items():
            domain_info.append(domain)
            print(" ", color("bold_red", domain + ":"), color("red", "", reset="red"))
            dump_dict(config, reset="red")
            print(color("reset"))

    if res["warn"]:
        print(color("bold_white", "Incorrect config"))
        for domain, config in res["warn"].items():
            domain_info.append(domain)
            print(
                " ",
                color("bold_yellow", domain + ":"),
                color("yellow", "", reset="yellow"),
            )
            dump_dict(config, reset="yellow")
            print(color("reset"))

    if domain_info:
        if "all" in domain_info:
            print(color("bold_white", "Successful config (all)"))
            for domain, config in res["components"].items():
                print(" ", color(C_HEAD, domain + ":"))
                dump_dict(config)
        else:
            print(color("bold_white", "Successful config (partial)"))
            for domain in domain_info:
                if domain == ERROR_STR:
                    continue
                print(" ", color(C_HEAD, domain + ":"))
                dump_dict(res["components"].get(domain))

    if args.secrets:
        flatsecret: dict[str, str] = {}

        for sfn, sdict in res["secret_cache"].items():
            sss = []
            for skey in sdict:
                if skey in flatsecret:
                    _LOGGER.error(
                        "Duplicated secrets in files %s and %s", flatsecret[skey], sfn
                    )
                flatsecret[skey] = sfn
                sss.append(color("green", skey) if skey in res["secrets"] else skey)
            print(color(C_HEAD, "Secrets from", sfn + ":"), ", ".join(sss))

        print(color(C_HEAD, "Used Secrets:"))
        for skey, sval in res["secrets"].items():
            if sval is None:
                print(" -", skey + ":", color("red", "not found"))
                continue
            print(" -", skey + ":", sval)

    return len(res["except"])


def check(config_dir, secrets=False):
    """Perform a check by mocking hass load functions."""
    logging.getLogger("homeassistant.loader").setLevel(logging.CRITICAL)
    res: dict[str, Any] = {
        "yaml_files": OrderedDict(),  # yaml_files loaded
        "secrets": OrderedDict(),  # secret cache and secrets loaded
        "except": OrderedDict(),  # critical exceptions raised (with config)
        "warn": OrderedDict(),  # non critical exceptions raised (with config)
        #'components' is a HomeAssistantConfig  # noqa: E265
        "secret_cache": {},
    }

    # pylint: disable-next=possibly-unused-variable
    def mock_load(filename, secrets=None):
        """Mock hass.util.load_yaml to save config file names."""
        res["yaml_files"][filename] = True
        return MOCKS["load"][1](filename, secrets)

    # pylint: disable-next=possibly-unused-variable
    def mock_secrets(ldr, node):
        """Mock _get_secrets."""
        try:
            val = MOCKS["secrets"][1](ldr, node)
        except HomeAssistantError:
            val = None
        res["secrets"][node.value] = val
        return val

    # Patches with local mock functions
    for key, val in MOCKS.items():
        if not secrets and key == "secrets":
            continue
        # The * in the key is removed to find the mock_function (side_effect)
        # This allows us to use one side_effect to patch multiple locations
        mock_function = locals()[f"mock_{key.replace('*', '')}"]
        PATCHES[key] = patch(val[0], side_effect=mock_function)

    # Start all patches
    for pat in PATCHES.values():
        pat.start()

    if secrets:
        # Ensure !secrets point to the patched function
        yaml_loader.add_constructor("!secret", yaml_loader.secret_yaml)

    def secrets_proxy(*args):
        secrets = Secrets(*args)
        res["secret_cache"] = secrets._cache  # pylint: disable=protected-access
        return secrets

    try:
        with patch.object(yaml_loader, "Secrets", secrets_proxy):
            res["components"] = asyncio.run(async_check_config(config_dir))
        res["secret_cache"] = {
            str(key): val for key, val in res["secret_cache"].items()
        }
        for err in res["components"].errors:
            domain = err.domain or ERROR_STR
            res["except"].setdefault(domain, []).append(err.message)
            if err.config:
                res["except"].setdefault(domain, []).append(err.config)

        for err in res["components"].warnings:
            domain = err.domain or WARNING_STR
            res["warn"].setdefault(domain, []).append(err.message)
            if err.config:
                res["warn"].setdefault(domain, []).append(err.config)

    except Exception as err:  # pylint: disable=broad-except
        print(color("red", "Fatal error while loading config:"), str(err))
        res["except"].setdefault(ERROR_STR, []).append(str(err))
    finally:
        # Stop all patches
        for pat in PATCHES.values():
            pat.stop()
        if secrets:
            # Ensure !secrets point to the original function
            yaml_loader.add_constructor("!secret", yaml_loader.secret_yaml)

    return res


async def async_check_config(config_dir):
    """Check the HA config."""
    hass = core.HomeAssistant(config_dir)
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await ar.async_load(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    await ir.async_load(hass, read_only=True)
    components = await async_check_ha_config_file(hass)
    await hass.async_stop(force=True)
    return components


def line_info(obj, **kwargs):
    """Display line config source."""
    if hasattr(obj, "__config_file__"):
        return color(
            "cyan", f"[source {obj.__config_file__}:{obj.__line__ or '?'}]", **kwargs
        )
    return "?"


def dump_dict(layer, indent_count=3, listi=False, **kwargs):
    """Display a dict.

    A friendly version of print yaml_loader.yaml.dump(config).
    """

    def sort_dict_key(val):
        """Return the dict key for sorting."""
        key = str(val[0]).lower()
        return "0" if key == "platform" else key

    indent_str = indent_count * " "
    if listi or isinstance(layer, list):
        indent_str = indent_str[:-1] + "-"
    if isinstance(layer, Mapping):
        for key, value in sorted(layer.items(), key=sort_dict_key):
            if isinstance(value, (dict, list)):
                print(indent_str, str(key) + ":", line_info(value, **kwargs))
                dump_dict(value, indent_count + 2, **kwargs)
            else:
                print(indent_str, str(key) + ":", value, line_info(key, **kwargs))
            indent_str = indent_count * " "
    if isinstance(layer, Sequence):
        for i in layer:
            if isinstance(i, dict):
                dump_dict(i, indent_count + 2, True, **kwargs)
            else:
                print(" ", indent_str, i)
