#!/usr/bin/env python3
"""
Generate an updated requirements_all.txt
"""

from collections import OrderedDict
import importlib
import os
import pkgutil
import re
import argparse

COMMENT_REQUIREMENTS = [
    'RPi.GPIO',
    'Adafruit_Python_DHT'
]


def explore_module(package, explore_children):
    """ Explore the modules. """
    module = importlib.import_module(package)

    found = []

    if not hasattr(module, '__path__'):
        return found

    for _, name, ispkg in pkgutil.iter_modules(module.__path__, package + '.'):
        found.append(name)

        if explore_children:
            found.extend(explore_module(name, False))

    return found


def core_requirements():
    """ Gather core requirements out of setup.py. """
    with open('setup.py') as inp:
        reqs_raw = re.search(
            r'REQUIRES = \[(.*?)\]', inp.read(), re.S).group(1)
    return re.findall(r"'(.*?)'", reqs_raw)


def comment_requirement(req):
    """ Some requirements don't install on all systems. """
    return any(ign in req for ign in COMMENT_REQUIREMENTS)


def gather_modules():
    """ Collect the information and construct the output. """
    reqs = OrderedDict()

    errors = []
    output = []

    for package in sorted(explore_module('homeassistant.components', True)):
        try:
            module = importlib.import_module(package)
        except ImportError:
            errors.append(package)
            continue
        # For catching the error by RPi.GPIO
        # RuntimeError: This module can only be run on a Raspberry Pi!
        except RuntimeError:
            continue

        if not getattr(module, 'REQUIREMENTS', None):
            continue

        for req in module.REQUIREMENTS:
            reqs.setdefault(req, []).append(package)

    if errors:
        print("Found errors")
        print('\n'.join(errors))
        return

    output.append('# Home Assistant core')
    output.append('\n')
    output.append('\n'.join(core_requirements()))
    output.append('\n')
    for pkg, requirements in reqs.items():
        for req in sorted(requirements,
                          key=lambda name: (len(name.split('.')), name)):
            output.append('\n# {}'.format(req))

        if comment_requirement(pkg):
            output.append('\n# {}\n'.format(pkg))
        else:
            output.append('\n{}\n'.format(pkg))

    return ''.join(output)


def write_file(data):
    """ Writes the modules to the requirements_all.txt. """
    with open('requirements_all.txt', 'w+') as req_file:
        req_file.write(data)


def display(data):
    """ Prints the output to command line. """
    print(data)


def argparsing():
    """ Parsing the command line arguments. """
    parser = argparse.ArgumentParser(
        description='Generate a requirements_all.txt')
    parser.add_argument('file', nargs='?',
                        help='create new requirements_all.txt file')
    return parser.parse_args()


def main():
    """ Main """
    if not os.path.isfile('requirements_all.txt'):
        print('Run this from HA root dir')
        return
    args = argparsing()
    data = gather_modules()

    if args.file:
        write_file(data)
    else:
        display(data)

if __name__ == '__main__':
    main()
