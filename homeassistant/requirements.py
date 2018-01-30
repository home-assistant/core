"""Module to handle installing requirements."""
import asyncio
from functools import partial
import logging
import os

import homeassistant.util.package as pkg_util

DATA_PIP_LOCK = 'pip_lock'
CONSTRAINT_FILE = 'package_constraints.txt'
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_process_requirements(hass, name, requirements):
    """Install the requirements for a component or platform.

    This method is a coroutine.
    """
    pip_lock = hass.data.get(DATA_PIP_LOCK)
    if pip_lock is None:
        pip_lock = hass.data[DATA_PIP_LOCK] = asyncio.Lock(loop=hass.loop)

    pip_install = partial(pkg_util.install_package,
                          **pip_kwargs(hass.config.config_dir))

    with (yield from pip_lock):
        for req in requirements:
            ret = yield from hass.async_add_job(pip_install, req)
            if not ret:
                _LOGGER.error("Not initializing %s because could not install "
                              "requirement %s", name, req)
                return False

    return True


def pip_kwargs(config_dir):
    """Return keyword arguments for PIP install."""
    kwargs = {
        'constraints': os.path.join(os.path.dirname(__file__), CONSTRAINT_FILE)
    }
    if not pkg_util.running_under_virtualenv():
        kwargs['target'] = os.path.join(config_dir, 'deps')
    return kwargs
