"""Home Assistant command line scripts."""

import importlib
import logging
import os
import sys

from homeassistant.requirements import pip_kwargs
from homeassistant.util.package import install_package, is_installed

# mypy: allow-untyped-defs, disallow-any-generics, no-warn-return-any


def run(args: list[str]) -> int:
    """Run a script."""
    scripts = []
    path = os.path.dirname(__file__)
    for fil in os.listdir(path):
        if fil == "__pycache__":
            continue

        if os.path.isdir(os.path.join(path, fil)):
            scripts.append(fil)
        elif fil != "__init__.py" and fil.endswith(".py"):
            scripts.append(fil[:-3])

    if not args:
        print("Please specify a script to run.")
        print("Available scripts:", ", ".join(scripts))
        return 1

    if args[0] not in scripts:
        print("Invalid script specified.")
        print("Available scripts:", ", ".join(scripts))
        return 1

    script = importlib.import_module(f"homeassistant.scripts.{args[0]}")

    _pip_kwargs = pip_kwargs()

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    for req in getattr(script, "REQUIREMENTS", []):
        if is_installed(req):
            continue

        if not install_package(req, **_pip_kwargs):
            print("Aborting script, could not install dependency", req)
            return 1

    return script.run(args[1:])
