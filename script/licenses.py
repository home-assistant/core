"""Tool to check the licenses."""

from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import sys

from awesomeversion import AwesomeVersion


@dataclass
class PackageDefinition:
    """Package definition."""

    license: str
    name: str
    version: AwesomeVersion

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> PackageDefinition:
        """Create a package definition from a dictionary."""
        return cls(
            license=data["License"],
            name=data["Name"],
            version=AwesomeVersion(data["Version"]),
        )


OSI_APPROVED_LICENSES = {
    "Academic Free License (AFL)",
    "Apache Software License",
    "Apple Public Source License",
    "Artistic License",
    "Attribution Assurance License",
    "BSD License",
    "Boost Software License 1.0 (BSL-1.0)",
    "CEA CNRS Inria Logiciel Libre License, version 2.1 (CeCILL-2.1)",
    "Common Development and Distribution License 1.0 (CDDL-1.0)",
    "Common Public License",
    "Eclipse Public License 1.0 (EPL-1.0)",
    "Eclipse Public License 2.0 (EPL-2.0)",
    "Educational Community License, Version 2.0 (ECL-2.0)",
    "Eiffel Forum License",
    "European Union Public Licence 1.0 (EUPL 1.0)",
    "European Union Public Licence 1.1 (EUPL 1.1)",
    "European Union Public Licence 1.2 (EUPL 1.2)",
    "GNU Affero General Public License v3",
    "GNU Affero General Public License v3 or later (AGPLv3+)",
    "GNU Free Documentation License (FDL)",
    "GNU General Public License (GPL)",
    "GNU General Public License v2 (GPLv2)",
    "GNU General Public License v2 or later (GPLv2+)",
    "GNU General Public License v3 (GPLv3)",
    "GNU General Public License v3 or later (GPLv3+)",
    "GNU Lesser General Public License v2 (LGPLv2)",
    "GNU Lesser General Public License v2 or later (LGPLv2+)",
    "GNU Lesser General Public License v3 (LGPLv3)",
    "GNU Lesser General Public License v3 or later (LGPLv3+)",
    "GNU Library or Lesser General Public License (LGPL)",
    "Historical Permission Notice and Disclaimer (HPND)",
    "IBM Public License",
    "ISC License (ISCL)",
    "Intel Open Source License",
    "Jabber Open Source License",
    "MIT License",
    "MIT No Attribution License (MIT-0)",
    "MITRE Collaborative Virtual Workspace License (CVW)",
    "MirOS License (MirOS)",
    "Motosoto License",
    "Mozilla Public License 1.0 (MPL)",
    "Mozilla Public License 1.1 (MPL 1.1)",
    "Mozilla Public License 2.0 (MPL 2.0)",
    "Mulan Permissive Software License v2 (MulanPSL-2.0)",
    "NASA Open Source Agreement v1.3 (NASA-1.3)",
    "Nethack General Public License",
    "Nokia Open Source License",
    "Open Group Test Suite License",
    "Open Software License 3.0 (OSL-3.0)",
    "PostgreSQL License",
    "Python License (CNRI Python License)",
    "Python Software Foundation License",
    "Qt Public License (QPL)",
    "Ricoh Source Code Public License",
    "SIL Open Font License 1.1 (OFL-1.1)",
    "Sleepycat License",
    "Sun Industry Standards Source License (SISSL)",
    "Sun Public License",
    "The Unlicense (Unlicense)",
    "Universal Permissive License (UPL)",
    "University of Illinois/NCSA Open Source License",
    "Vovida Software License 1.0",
    "W3C License",
    "X.Net License",
    "Zero-Clause BSD (0BSD)",
    "Zope Public License",
    "zlib/libpng License",
    "Apache License",
    "MIT",
    "apache-2.0",
    "GPL-3.0",
    "GPLv3+",
    "MPL2",
    "MPL-2.0",
    "Apache 2",
    "LGPL v3",
    "BSD",
    "GNU-3.0",
    "GPLv3",
    "Eclipse Public License v2.0",
    "ISC",
    "GPL-2.0-only",
    "mit",
    "GNU General Public License v3",
    "Unlicense",
    "Apache-2",
    "GPLv2",
    "Python-2.0.1",
}

EXCEPTIONS = {
    "PyMicroBot",  # https://github.com/spycle/pyMicroBot/pull/3
    "PySwitchmate",  # https://github.com/Danielhiversen/pySwitchmate/pull/16
    "PyXiaomiGateway",  # https://github.com/Danielhiversen/PyXiaomiGateway/pull/201
    "aiocomelit",  # https://github.com/chemelli74/aiocomelit/pull/138
    "aioecowitt",  # https://github.com/home-assistant-libs/aioecowitt/pull/180
    "aioopenexchangerates",  # https://github.com/MartinHjelmare/aioopenexchangerates/pull/94
    "aiooui",  # https://github.com/Bluetooth-Devices/aiooui/pull/8
    "aioruuvigateway",  # https://github.com/akx/aioruuvigateway/pull/6
    "aiovodafone",  # https://github.com/chemelli74/aiovodafone/pull/131
    "apple_weatherkit",  # https://github.com/tjhorner/python-weatherkit/pull/3
    "asyncio",  # PSF License
    "chacha20poly1305",  # LGPL
    "chacha20poly1305-reuseable",  # Apache 2.0 or BSD 3-Clause
    "commentjson",  # https://github.com/vaidik/commentjson/pull/55
    "crownstone-cloud",  # https://github.com/crownstone/crownstone-lib-python-cloud/pull/5
    "crownstone-core",  # https://github.com/crownstone/crownstone-lib-python-core/pull/6
    "crownstone-sse",  # https://github.com/crownstone/crownstone-lib-python-sse/pull/2
    "crownstone-uart",  # https://github.com/crownstone/crownstone-lib-python-uart/pull/12
    "eliqonline",  # https://github.com/molobrakos/eliqonline/pull/17
    "enocean",  # https://github.com/kipe/enocean/pull/142
    "gardena-bluetooth",  # https://github.com/elupus/gardena-bluetooth/pull/11
    "heatmiserV3",  # https://github.com/andylockran/heatmiserV3/pull/94
    "huum",  # https://github.com/frwickst/pyhuum/pull/8
    "imutils",  # https://github.com/PyImageSearch/imutils/pull/292
    "iso4217",  # Public domain
    "kiwiki_client",  # https://github.com/c7h/kiwiki_client/pull/6
    "krakenex",  # https://github.com/veox/python3-krakenex/pull/145
    "ld2410-ble",  # https://github.com/930913/ld2410-ble/pull/7
    "maxcube-api",  # https://github.com/uebelack/python-maxcube-api/pull/48
    "neurio",  # https://github.com/jordanh/neurio-python/pull/13
    "nsw-fuel-api-client",  # https://github.com/nickw444/nsw-fuel-api-client/pull/14
    "pigpio",  # https://github.com/joan2937/pigpio/pull/608
    "pymitv",  # MIT
    "pybbox",  # https://github.com/HydrelioxGitHub/pybbox/pull/5
    "pyeconet",  # https://github.com/w1ll1am23/pyeconet/pull/41
    "pysabnzbd",  # https://github.com/jeradM/pysabnzbd/pull/6
    "pyvera",  # https://github.com/maximvelichko/pyvera/pull/164
    "pyxeoma",  # https://github.com/jeradM/pyxeoma/pull/11
    "repoze.lru",
    "ruuvitag-ble",  # https://github.com/Bluetooth-Devices/ruuvitag-ble/pull/10
    "sensirion-ble",  # https://github.com/akx/sensirion-ble/pull/9
    "sharp_aquos_rc",  # https://github.com/jmoore987/sharp_aquos_rc/pull/14
    "tapsaff",  # https://github.com/bazwilliams/python-taps-aff/pull/5
    "vincenty",  # Public domain
    "zeversolar",  # https://github.com/kvanzuijlen/zeversolar/pull/46
    # Using License-Expression (with hatchling)
    "ftfy",  # Apache-2.0
}

TODO = {
    "aiocache": AwesomeVersion(
        "0.12.3"
    ),  # https://github.com/aio-libs/aiocache/blob/master/LICENSE all rights reserved?
}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the main script."""
    exit_code = 0

    parser = ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        default="licenses.json",
        help="Path to json licenses file",
    )

    argv = argv or sys.argv[1:]
    args = parser.parse_args(argv)

    raw_licenses = json.loads(Path(args.path).read_text())
    package_definitions = [PackageDefinition.from_dict(data) for data in raw_licenses]
    for package in package_definitions:
        previous_unapproved_version = TODO.get(package.name)
        approved = False
        for approved_license in OSI_APPROVED_LICENSES:
            if approved_license in package.license:
                approved = True
                break
        if previous_unapproved_version is not None:
            if previous_unapproved_version < package.version:
                if approved:
                    print(
                        "Approved license detected for "
                        f"{package.name}@{package.version}: {package.license}"
                    )
                    print("Please remove the package from the TODO list.")
                    print()
                else:
                    print(
                        "We could not detect an OSI-approved license for "
                        f"{package.name}@{package.version}: {package.license}"
                    )
                    print()
                exit_code = 1
        elif not approved and package.name not in EXCEPTIONS:
            print(
                "We could not detect an OSI-approved license for "
                f"{package.name}@{package.version}: {package.license}"
            )
            print()
            exit_code = 1
        elif approved and package.name in EXCEPTIONS:
            print(
                "Approved license detected for "
                f"{package.name}@{package.version}: {package.license}"
            )
            print(f"Please remove the package from the EXCEPTIONS list: {package.name}")
            print()
            exit_code = 1
    current_packages = {package.name for package in package_definitions}
    for package in [*TODO.keys(), *EXCEPTIONS]:
        if package not in current_packages:
            print(
                f"Package {package} is tracked, but not used. Please remove from the licenses.py"
                "file."
            )
            print()
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    if exit_code == 0:
        print("All licenses are approved!")
    sys.exit(exit_code)
