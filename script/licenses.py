"""Tool to check the licenses."""

from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Flag, auto
import json
import logging
from pathlib import Path
import sys

from awesomeversion import AwesomeVersion
from license_expression import (
    AND,
    OR,
    ExpressionError,
    LicenseExpression,
    LicenseSymbol,
    get_spdx_licensing,
)

licensing = get_spdx_licensing()
logger = logging.getLogger(__name__)


@dataclass
class PackageDefinition:
    """Package definition."""

    license_classifier: list[str]
    license_metadata: str
    name: str
    version: AwesomeVersion

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> PackageDefinition:
        """Create a package definition from a dictionary."""
        return cls(
            license_classifier=data["License-Classifier"].split("; "),
            license_metadata=data["License-Metadata"],
            name=data["Name"],
            version=AwesomeVersion(data["Version"]),
        )


# Incomplete list of OSI approved SPDX identifiers
# Add more as needed, see https://spdx.org/licenses/
OSI_APPROVED_LICENSES_SPDX = {
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "HPND",
    "ISC",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "MIT",
    "MPL-2.0",
    "PSF-2.0",  # not approved
    "Python-2.0.1",  # not approved
    "Unlicense",
}

OSI_APPROVED_LICENSE_CLASSIFIER = {
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
    "zeversolar",  # https://github.com/kvanzuijlen/zeversolar/pull/46
    # Using License-Expression (with hatchling)
    "ftfy",  # Apache-2.0
}

TODO = {
    "aiocache": AwesomeVersion(
        "0.12.3"
    ),  # https://github.com/aio-libs/aiocache/blob/master/LICENSE all rights reserved?
    # -- Full license text in metadata
    "PyNINA": AwesomeVersion("0.3.3"),  # MIT
    "aioconsole": AwesomeVersion("0.8.0"),  # GPL
    "dicttoxml": AwesomeVersion("1.7.16"),  # GPL
    "homematicip": AwesomeVersion("1.1.2"),  # GPL
    "ibmiotf": AwesomeVersion("0.3.4"),  # Eclipse Public License
    "matrix-nio": AwesomeVersion("0.25.2"),  # ISC
    "zwave-js-server-python": AwesomeVersion(
        "0.58.1"
    ),  # Apache  # https://github.com/home-assistant-libs/zwave-js-server-python/pull/1029
    # -- Not SPDX license strings --
    "PyNaCl": AwesomeVersion("1.5.0"),  # Apache License 2.0
    "PySocks": AwesomeVersion("1.7.1"),  # BSD
    "aioairq": AwesomeVersion("0.3.2"),  # Apache License, Version 2.0
    "aioaquacell": AwesomeVersion("0.2.0"),  # Apache License 2.0
    "aioeagle": AwesomeVersion("1.1.0"),  # Apache License 2.0
    "aiohttp_socks": AwesomeVersion("0.9.0"),  # Apache 2
    "aiolivisi": AwesomeVersion("0.0.19"),  # Apache License 2.0
    "aiopegelonline": AwesomeVersion("0.0.10"),  # Apache License 2.0
    "aioshelly": AwesomeVersion("12.0.0"),  # Apache License 2.0
    "amcrest": AwesomeVersion("1.9.8"),  # GPLv2
    "async-modbus": AwesomeVersion("0.2.1"),  # GNU General Public License v3
    "asyncssh": AwesomeVersion("2.17.0"),  # Eclipse Public License v2.0
    "baidu-aip": AwesomeVersion("1.6.6.0"),  # Apache License
    "bs4": AwesomeVersion("0.0.2"),  # MIT License
    "bt-proximity": AwesomeVersion("0.2.1"),  # Apache 2.0
    "connio": AwesomeVersion("0.2.0"),  # GPLv3+
    "datapoint": AwesomeVersion("0.9.9"),  # GPLv3
    "electrickiwi-api": AwesomeVersion("0.8.5"),  # GNU-3.0
    "freebox-api": AwesomeVersion("1.1.0"),  # GNU GPL v3
    "gpiod": AwesomeVersion("2.2.1"),  # LGPLv2.1
    "insteon-frontend-home-assistant": AwesomeVersion("0.5.0"),  # MIT License
    "knx_frontend": AwesomeVersion("2024.9.10.221729"),  # MIT License
    "lcn-frontend": AwesomeVersion("0.1.6"),  # MIT License
    "libpyfoscam": AwesomeVersion("1.2.2"),  # LGPLv3+
    "london-tube-status": AwesomeVersion("0.5"),  # Apache License, Version 2.0
    "mutesync": AwesomeVersion("0.0.1"),  # Apache License 2.0
    "oemthermostat": AwesomeVersion("1.1.1"),  # BSD
    "paho-mqtt": AwesomeVersion(
        "1.6.1"
    ),  # Eclipse Public License v2.0 / Eclipse Distribution License v1.0
    "pilight": AwesomeVersion("0.1.1"),  # MIT License
    "ply": AwesomeVersion("3.11"),  # BSD
    "protobuf": AwesomeVersion("5.28.2"),  # 3-Clause BSD License
    "psutil-home-assistant": AwesomeVersion("0.0.1"),  # Apache License 2.0
    "pure-pcapy3": AwesomeVersion("1.0.1"),  # Simplified BSD
    "py-vapid": AwesomeVersion("1.9.1"),  # MPL2
    "pyAtome": AwesomeVersion("0.1.1"),  # Apache Software License
    "pybotvac": AwesomeVersion("0.0.25"),  # Licensed under the MIT license
    "pychannels": AwesomeVersion("1.2.3"),  # The MIT License
    "pycognito": AwesomeVersion("2024.5.1"),  # Apache License 2.0
    "pycountry": AwesomeVersion("23.12.11"),  # LGPL 2.1
    "pycryptodome": AwesomeVersion("3.21.0"),  # BSD, Public Domain
    "pycryptodomex": AwesomeVersion("3.21.0"),  # BSD, Public Domain
    "pydanfossair": AwesomeVersion("0.1.0"),  # Apache 2.0
    "pydrawise": AwesomeVersion("2024.9.0"),  # Apache License 2.0
    "pydroid-ipcam": AwesomeVersion("2.0.0"),  # Apache License 2.0
    "pyebox": AwesomeVersion("1.1.4"),  # Apache 2.0
    "pyevilgenius": AwesomeVersion("2.0.0"),  # Apache License 2.0
    "pyezviz": AwesomeVersion("0.2.1.2"),  # Apache Software License 2.0
    "pyfido": AwesomeVersion("2.1.2"),  # Apache 2.0
    "pyialarm": AwesomeVersion("2.2.0"),  # Apache 2.0
    "pylitejet": AwesomeVersion("0.6.3"),  # MIT License
    "pyquery": AwesomeVersion("2.0.1"),  # BSD
    "pyschlage": AwesomeVersion("2024.8.0"),  # Apache License 2.0
    "pysuez": AwesomeVersion("0.2.0"),  # Apache 2.0
    "python-digitalocean": AwesomeVersion("1.13.2"),  # LGPL v3
    "python-socks": AwesomeVersion("2.5.3"),  # Apache 2
    "pywebpush": AwesomeVersion("1.14.1"),  # MPL2
    "raincloudy": AwesomeVersion("0.0.7"),  # Apache License 2.0
    "securetar": AwesomeVersion("2024.2.1"),  # Apache License 2.0
    "simplehound": AwesomeVersion("0.3"),  # Apache License, Version 2.0
    "sockio": AwesomeVersion("0.15.0"),  # GPLv3+
    "starkbank-ecdsa": AwesomeVersion("2.2.0"),  # MIT License
    "streamlabswater": AwesomeVersion("1.0.1"),  # Apache 2.0
    "vilfo-api-client": AwesomeVersion("0.5.0"),  # MIT License
    "voluptuous-openapi": AwesomeVersion("0.0.5"),  # Apache License 2.0
    "voluptuous-serialize": AwesomeVersion("2.6.0"),  # Apache License 2.0
    "vultr": AwesomeVersion("0.1.2"),  # The MIT License (MIT)
    "wallbox": AwesomeVersion("0.7.0"),  # Apache 2
    "zeroconf": AwesomeVersion("0.135.0"),  # LGPL
    "zha-quirks": AwesomeVersion("0.0.123"),  # Apache License Version 2.0
    "zhong-hong-hvac": AwesomeVersion("1.0.13"),  # Apache
}

EXCEPTIONS_AND_TODOS = EXCEPTIONS.union(TODO.keys())


def check_spdx_license(expr: LicenseExpression) -> bool:
    """Check a spdx license expression."""
    if isinstance(expr, LicenseSymbol):
        return expr.key in OSI_APPROVED_LICENSES_SPDX
    if isinstance(expr, OR):
        return any(check_spdx_license(arg) for arg in expr.args)
    if isinstance(expr, AND):
        return all(check_spdx_license(arg) for arg in expr.args)
    return False


def check_license_metadata(license: str, package_name: str) -> bool | None:
    """Check if license metadata is a valid and approved SPDX license string."""
    if license == "UNKNOWN" or "\n" in license:
        # Ignore mulitline license strings
        # Those are often full license texts which discurraged
        return None
    try:
        expr = licensing.parse(license, validate=True)
    except ExpressionError:
        logger.debug(
            "Not a validate metadata license for %s: %s",
            package_name,
            license,
        )
        return None
    return check_spdx_license(expr)


def check_license_classifier(licenses: list[str], package_name: str) -> bool | None:
    """Check license classifier are OSI approved."""
    assert len(licenses) > 0
    if licenses[0] == "UNKNOWN":
        return None
    if len(licenses) > 1:
        # It's not defined how multiple license classifier should be interpreted
        # To be safe required ALL to be approved
        check = all(
            classifier in OSI_APPROVED_LICENSE_CLASSIFIER for classifier in licenses
        )
        if check is False:
            logger.debug(
                "Not all classifier approved for %s: %s", package_name, licenses
            )
        return check
    return licenses[0] in OSI_APPROVED_LICENSE_CLASSIFIER


class Status(Flag):
    """License status flag."""

    APPROVED = auto()
    NOT_APPROVED = auto()
    METADATA = auto()
    CLASSIFIER = auto()
    UNKNOWN = auto()


def determine_license_status(package: PackageDefinition) -> Status:
    """Determine license status.

    First, check license metadata then license classifier.
    """
    check = check_license_metadata(package.license_metadata, package.name)
    if check is True:
        return Status.APPROVED | Status.METADATA
    if check is False:
        return Status.NOT_APPROVED | Status.METADATA

    check = check_license_classifier(package.license_classifier, package.name)
    if check is True:
        return Status.APPROVED | Status.CLASSIFIER
    if check is False:
        return Status.NOT_APPROVED | Status.CLASSIFIER

    return Status.NOT_APPROVED | Status.UNKNOWN


def get_license_str(pkg: PackageDefinition, status: Status) -> str:
    """Return combined license string."""
    return f"{pkg.license_metadata} -- {pkg.license_classifier}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the main script."""
    exit_code = 0
    logging.basicConfig(
        format="%(levelname)s:%(message)s", stream=sys.stdout, level=logging.INFO
    )

    parser = ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        default="licenses.json",
        help="Path to json licenses file",
    )
    parser.add_argument(
        "-v", dest="verbose", action="store_true", help="Enable verbose logging"
    )

    argv = argv or sys.argv[1:]
    args = parser.parse_args(argv)
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    raw_licenses = json.loads(Path(args.path).read_text())
    license_status: dict[str, tuple[PackageDefinition, Status]] = {
        package.name: (package, determine_license_status(package))
        for data in raw_licenses
        if (package := PackageDefinition.from_dict(data))
    }

    for package_name, version in TODO.items():
        pkg, status = license_status.get(package_name, (None, None))
        if pkg is None or not (version < pkg.version):
            continue
        assert status
        if Status.APPROVED in status:
            print(
                "Approved license detected for "
                f"{pkg.name}@{pkg.version}: {get_license_str(pkg, status)}\n"
                "Please remove the package from the TODO list.\n"
            )
        else:
            print(
                "We could not detect an OSI-approved license for "
                f"{pkg.name}@{pkg.version}: {get_license_str(pkg, status)}\n"
                "Please update the package version on the TODO list.\n"
            )
        exit_code = 1

    for pkg, status in license_status.values():
        if Status.NOT_APPROVED in status and pkg.name not in EXCEPTIONS_AND_TODOS:
            print(
                "We could not detect an OSI-approved license for "
                f"{pkg.name}@{pkg.version}: {get_license_str(pkg, status)}\n"
            )
            exit_code = 1
        elif Status.APPROVED in status and pkg.name in EXCEPTIONS:
            print(
                "Approved license detected for "
                f"{pkg.name}@{pkg.version}: {get_license_str(pkg, status)}\n"
                f"Please remove the package from the EXCEPTIONS list: {pkg.name}\n"
            )
            exit_code = 1

    for package_name in EXCEPTIONS_AND_TODOS.difference(license_status.keys()):
        print(
            f"Package {package_name} is tracked, but not used. "
            "Please remove from the licenses.py file.\n"
        )
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    exit_code = main()
    if exit_code == 0:
        print("All licenses are approved!")
    sys.exit(exit_code)
