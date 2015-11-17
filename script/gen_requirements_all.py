#!/usr/bin/env python3
"""
Generate an updated requirements_all.txt
"""

from collections import OrderedDict
import importlib
import os
import pkgutil
import re


def explore_module(package, explore_children):
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
    with open('setup.py') as inp:
        reqs_raw = re.search(
            r'REQUIRES = \[(.*?)\]', inp.read(), re.S).group(1)

    return re.findall(r"'(.*?)'", reqs_raw)


def main():
    if not os.path.isfile('requirements_all.txt'):
        print('Run this from HA root dir')
        return

    reqs = OrderedDict()

    errors = []
    for package in sorted(explore_module('homeassistant.components', True)):
        try:
            module = importlib.import_module(package)
        except ImportError:
            errors.append(package)
            continue

        if not getattr(module, 'REQUIREMENTS', None):
            continue

        for req in module.REQUIREMENTS:
            reqs.setdefault(req, []).append(package)

    if errors:
        print("Found errors")
        print('\n'.join(errors))
        return

    print('# Home Assistant core')
    print('\n'.join(core_requirements()))
    print()

    for pkg, requirements in reqs.items():
        for req in sorted(requirements,
                          key=lambda name: (len(name.split('.')), name)):
            print('#', req)
        print(pkg)
        print()

if __name__ == '__main__':
    main()
