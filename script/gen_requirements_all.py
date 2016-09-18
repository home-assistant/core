#!/usr/bin/env python3
"""Generate an updated requirements_all.txt."""
import importlib
import os
import pkgutil
import re
import sys

COMMENT_REQUIREMENTS = (
    'RPi.GPIO',
    'rpi-rf',
    'Adafruit_Python_DHT',
    'fritzconnection',
    'pybluez',
    'bluepy',
    'python-lirc',
    'gattlib',
    'pyuserinput',
)

IGNORE_PACKAGES = (
    'homeassistant.components.recorder.models',
)


def explore_module(package, explore_children):
    """Explore the modules."""
    module = importlib.import_module(package)

    found = []

    if not hasattr(module, '__path__'):
        return found

    for _, name, _ in pkgutil.iter_modules(module.__path__, package + '.'):
        found.append(name)

        if explore_children:
            found.extend(explore_module(name, False))

    return found


def core_requirements():
    """Gather core requirements out of setup.py."""
    with open('setup.py') as inp:
        reqs_raw = re.search(
            r'REQUIRES = \[(.*?)\]', inp.read(), re.S).group(1)
    return re.findall(r"'(.*?)'", reqs_raw)


def comment_requirement(req):
    """Some requirements don't install on all systems."""
    return any(ign in req for ign in COMMENT_REQUIREMENTS)


def gather_modules():
    """Collect the information and construct the output."""
    reqs = {}

    errors = []
    output = []

    for package in sorted(explore_module('homeassistant.components', True) +
                          explore_module('homeassistant.scripts', True)):
        try:
            module = importlib.import_module(package)
        except ImportError:
            if package not in IGNORE_PACKAGES:
                errors.append(package)
            continue

        if not getattr(module, 'REQUIREMENTS', None):
            continue

        for req in module.REQUIREMENTS:
            reqs.setdefault(req, []).append(package)

    for key in reqs:
        reqs[key] = sorted(reqs[key],
                           key=lambda name: (len(name.split('.')), name))

    if errors:
        print("******* ERROR")
        print("Errors while importing: ", ', '.join(errors))
        print("Make sure you import 3rd party libraries inside methods.")
        return None

    output.append('# Home Assistant core')
    output.append('\n')
    output.append('\n'.join(core_requirements()))
    output.append('\n')
    for pkg, requirements in sorted(reqs.items(), key=lambda item: item[0]):
        for req in sorted(requirements,
                          key=lambda name: (len(name.split('.')), name)):
            output.append('\n# {}'.format(req))

        if comment_requirement(pkg):
            output.append('\n# {}\n'.format(pkg))
        else:
            output.append('\n{}\n'.format(pkg))

    return ''.join(output)


def write_file(data):
    """Write the modules to the requirements_all.txt."""
    with open('requirements_all.txt', 'w+') as req_file:
        req_file.write(data)


def validate_file(data):
    """Validate if requirements_all.txt is up to date."""
    with open('requirements_all.txt', 'r') as req_file:
        return data == ''.join(req_file)


def main():
    """Main section of the script."""
    if not os.path.isfile('requirements_all.txt'):
        print('Run this from HA root dir')
        return

    data = gather_modules()

    if data is None:
        sys.exit(1)

    if sys.argv[-1] == 'validate':
        if validate_file(data):
            sys.exit(0)
        print("******* ERROR")
        print("requirements_all.txt is not up to date")
        print("Please run script/gen_requirements_all.py")
        sys.exit(1)

    write_file(data)

if __name__ == '__main__':
    main()
