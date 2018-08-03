"""Module to handle installing requirements."""
import asyncio
from functools import partial
import logging
import os
from typing import List, Dict, Optional

import homeassistant.util.package as pkg_util
from homeassistant.core import HomeAssistant

DATA_PIP_LOCK = 'pip_lock'
CONSTRAINT_FILE = 'package_constraints.txt'
_LOGGER = logging.getLogger(__name__)


async def async_process_requirements(hass: HomeAssistant, name: str,
                                     requirements: List[str]) -> bool:
    """Install the requirements for a component or platform.

    This method is a coroutine.
    """
    pip_lock = hass.data.get(DATA_PIP_LOCK)
    if pip_lock is None:
        pip_lock = hass.data[DATA_PIP_LOCK] = asyncio.Lock(loop=hass.loop)

    pip_install = partial(pkg_util.install_package,
                          **pip_kwargs(hass.config.config_dir))

    async with pip_lock:
        for req in requirements:
            ret = await hass.async_add_executor_job(pip_install, req)
            if not ret:
                _LOGGER.error("Not initializing %s because could not install "
                              "requirement %s", name, req)
                return False

    return True


def pip_kwargs(config_dir: Optional[str]) -> Dict[str, str]:
    """Return keyword arguments for PIP install."""
    kwargs = {
        'constraints': os.path.join(os.path.dirname(__file__), CONSTRAINT_FILE)
    }
    if not (config_dir is None or pkg_util.is_virtual_env()):
        kwargs['target'] = os.path.join(config_dir, 'deps')
    return kwargs
