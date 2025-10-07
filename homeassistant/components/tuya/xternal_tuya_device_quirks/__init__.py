"""Quirks for Tuya."""

from __future__ import annotations

import importlib
import logging
import pathlib
import pkgutil
import sys

from ..xternal_tuya_quirks import TUYA_QUIRKS_REGISTRY

_LOGGER = logging.getLogger(__name__)


def register_tuya_quirks(custom_quirks_path: str | None = None) -> None:
    """Register all quirks with xternal_tuya_quirks.

    - remove custom quirks from `custom_quirks_path`
    - add quirks from `xternal_tuya_device_quirks`
    - add custom quirks from `custom_quirks_path`
    """

    if custom_quirks_path is not None:
        TUYA_QUIRKS_REGISTRY.purge_custom_quirks(custom_quirks_path)

    # Import all quirks in the `xternal_tuya_device_quirks` package first
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        path=__path__,
        prefix=__name__ + ".",
    ):
        _LOGGER.debug("Loading quirks module %r", modname)
        importlib.import_module(modname)

    if custom_quirks_path is None:
        return

    path = pathlib.Path(custom_quirks_path)
    _LOGGER.debug("Loading custom quirks from %r", path)

    loaded = False

    # Treat the custom quirk path (e.g. `/config/tuya_quirks/`) itself as a module
    for importer, modname, _ispkg in pkgutil.walk_packages(path=[str(path)]):
        _LOGGER.debug("Loading custom quirk module %r", modname)

        try:
            spec = importer.find_spec(modname)  # type: ignore[call-arg]
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            sys.modules[modname] = module
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception:
            _LOGGER.exception("Unexpected exception importing custom quirk %r", modname)
        else:
            loaded = True

    if loaded:
        _LOGGER.warning(
            "Loaded custom quirks. Please contribute them to https://github.com/TBD"
        )
