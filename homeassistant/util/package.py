"""Helpers to install PyPi packages."""
import os
import logging
import pkg_resources
import subprocess
import sys
import threading

_LOGGER = logging.getLogger(__name__)
INSTALL_LOCK = threading.Lock()


def install_package(package, upgrade=True, target=None):
    """Install a package on PyPi. Accepts pip compatible package strings.
    Return boolean if install successfull."""
    # Not using 'import pip; pip.main([])' because it breaks the logger
    args = [sys.executable, '-m', 'pip', 'install', '--quiet', package]

    if upgrade:
        args.append('--upgrade')
    if target:
        args += ['--target', os.path.abspath(target)]

    with INSTALL_LOCK:
        if check_package_exists(package, target):
            return True

        _LOGGER.info('Attempting install of %s', package)
        try:
            return 0 == subprocess.call(args)
        except subprocess.SubprocessError:
            return False


def check_package_exists(package, target=None):
    """Check if a package exists.
    Returns True when the requirement is met.
    Returns False when the package is not installed or doesn't meet req."""
    req = pkg_resources.Requirement.parse(package)

    if target:
        work_set = pkg_resources.WorkingSet([target])
        search_fun = work_set.find

    else:
        search_fun = pkg_resources.get_distribution

    try:
        result = search_fun(req)
    except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
        return False

    return bool(result)
