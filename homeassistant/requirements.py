"""Module to handle installing requirements."""
import asyncio
from pathlib import Path
import logging
import os
from typing import Any, Dict, List, Optional

import homeassistant.util.package as pkg_util
from homeassistant.core import HomeAssistant

DATA_PIP_LOCK = "pip_lock"
DATA_PKG_CACHE = "pkg_cache"
CONSTRAINT_FILE = "package_constraints.txt"
PROGRESS_FILE = ".pip_progress"
_LOGGER = logging.getLogger(__name__)


async def async_process_requirements(
    hass: HomeAssistant, name: str, requirements: List[str]
) -> bool:
    """Install the requirements for a component or platform.

    This method is a coroutine.
    """
    pip_lock = hass.data.get(DATA_PIP_LOCK)
    if pip_lock is None:
        pip_lock = hass.data[DATA_PIP_LOCK] = asyncio.Lock()

    kwargs = pip_kwargs(hass.config.config_dir)

    async with pip_lock:
        for req in requirements:
            if pkg_util.is_installed(req):
                continue

            ret = await hass.async_add_executor_job(_install, hass, req, kwargs)

            if not ret:
                _LOGGER.error(
                    "Not initializing %s because could not install " "requirement %s",
                    name,
                    req,
                )
                return False

    return True


def _install(hass: HomeAssistant, req: str, kwargs: Dict) -> bool:
    """Install requirement."""
    progress_path = Path(hass.config.path(PROGRESS_FILE))
    progress_path.touch()
    try:
        return pkg_util.install_package(req, **kwargs)
    finally:
        progress_path.unlink()


def pip_kwargs(config_dir: Optional[str]) -> Dict[str, Any]:
    """Return keyword arguments for PIP install."""
    is_docker = pkg_util.is_docker_env()
    kwargs = {
        "constraints": os.path.join(os.path.dirname(__file__), CONSTRAINT_FILE),
        "no_cache_dir": is_docker,
    }
    if "WHEELS_LINKS" in os.environ:
        kwargs["find_links"] = os.environ["WHEELS_LINKS"]
    if not (config_dir is None or pkg_util.is_virtual_env()) and not is_docker:
        kwargs["target"] = os.path.join(config_dir, "deps")
    return kwargs
