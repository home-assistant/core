"""Tool to check the licenses."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import metadata
import json
from pathlib import Path
import sys
from typing import TypedDict, cast

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


class PackageMetadata(TypedDict):
    """Package metadata."""

    name: str
    version: str
    license_expression: str | None
    license_metadata: str | None
    license_classifier: list[str]


@dataclass
class PackageDefinition:
    """Package definition."""

    license: str
    license_expression: str | None
    license_metadata: str | None
    license_classifier: list[str]
    name: str
    version: AwesomeVersion

    @classmethod
    def from_dict(cls, data: PackageMetadata) -> PackageDefinition:
        """Create a package definition from PackageMetadata."""
        if not (license_str := "; ".join(data["license_classifier"])):
            license_str = data["license_metadata"] or "UNKNOWN"
        return cls(
            license=license_str,
            license_expression=data["license_expression"],
            license_metadata=data["license_metadata"],
            license_classifier=data["license_classifier"],
            name=data["name"],
            version=AwesomeVersion(data["version"]),
        )


# Incomplete list of OSI approved SPDX identifiers
# Add more as needed, see https://spdx.org/licenses/
OSI_APPROVED_LICENSES_SPDX = {
    "0BSD",
    "AFL-2.1",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "Apache-2.0",
    "BSD-1-Clause",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "EPL-1.0",
    "EPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "HPND",
    "ISC",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "MIT",
    "MIT-CMU",
    "MPL-1.1",
    "MPL-2.0",
    "PSF-2.0",
    "Python-2.0",
    "Unlicense",
    "Zlib",
    "ZPL-2.1",
}

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
    # End license classifier
    "Apache License",
    "MIT",
    "MPL2",
    "Apache 2",
    "LGPL v3",
    "BSD",
    "GNU-3.0",
    "GPLv3",
    "Eclipse Public License v2.0",
    "ISC",
    "GNU General Public License v3",
    "GPLv2",
}

EXCEPTIONS = {
    "PyMicroBot",  # https://github.com/spycle/pyMicroBot/pull/3
    "PySwitchmate",  # https://github.com/Danielhiversen/pySwitchmate/pull/16
    "PyXiaomiGateway",  # https://github.com/Danielhiversen/PyXiaomiGateway/pull/201
    "chacha20poly1305",  # LGPL
    "commentjson",  # https://github.com/vaidik/commentjson/pull/55
    "crownstone-cloud",  # https://github.com/crownstone/crownstone-lib-python-cloud/pull/5
    "crownstone-core",  # https://github.com/crownstone/crownstone-lib-python-core/pull/6
    "crownstone-sse",  # https://github.com/crownstone/crownstone-lib-python-sse/pull/2
    "crownstone-uart",  # https://github.com/crownstone/crownstone-lib-python-uart/pull/12
    "eliqonline",  # https://github.com/molobrakos/eliqonline/pull/17
    "enocean",  # https://github.com/kipe/enocean/pull/142
    "imutils",  # https://github.com/PyImageSearch/imutils/pull/292
    "iso4217",  # Public domain
    "kiwiki_client",  # https://github.com/c7h/kiwiki_client/pull/6
    "ld2410-ble",  # https://github.com/930913/ld2410-ble/pull/7
    "maxcube-api",  # https://github.com/uebelack/python-maxcube-api/pull/48
    "neurio",  # https://github.com/jordanh/neurio-python/pull/13
    "nsw-fuel-api-client",  # https://github.com/nickw444/nsw-fuel-api-client/pull/14
    "pigpio",  # https://github.com/joan2937/pigpio/pull/608
    "pymitv",  # MIT
    "pybbox",  # https://github.com/HydrelioxGitHub/pybbox/pull/5
    "pysabnzbd",  # https://github.com/jeradM/pysabnzbd/pull/6
    "pyvera",  # https://github.com/maximvelichko/pyvera/pull/164
    "repoze.lru",
    "sharp_aquos_rc",  # https://github.com/jmoore987/sharp_aquos_rc/pull/14
    "tapsaff",  # https://github.com/bazwilliams/python-taps-aff/pull/5
    # ---
    # https://github.com/jaraco/skeleton/pull/170
    # https://github.com/jaraco/skeleton/pull/171
    "jaraco.itertools",  # MIT - https://github.com/jaraco/jaraco.itertools/issues/21
    "setuptools",  # MIT
}

TODO = {
    "aiocache": AwesomeVersion(
        "0.12.3"
    ),  # https://github.com/aio-libs/aiocache/blob/master/LICENSE all rights reserved?
}

EXCEPTIONS_AND_TODOS = EXCEPTIONS.union(TODO)


def check_licenses(args: CheckArgs) -> int:
    """Check licenses are OSI approved."""
    exit_code = 0
    raw_licenses = json.loads(Path(args.path).read_text())
    license_status = {
        pkg.name: (pkg, check_license_status(pkg))
        for data in raw_licenses
        if (pkg := PackageDefinition.from_dict(data))
    }

    for name, version in TODO.items():
        pkg, status = license_status.get(name, (None, None))
        if pkg is None or not (version < pkg.version):
            continue
        assert status is not None

        if status is True:
            print(
                "Approved license detected for "
                f"{pkg.name}@{pkg.version}: {get_license_str(pkg)}\n"
                "Please remove the package from the TODO list.\n"
            )
        else:
            print(
                "We could not detect an OSI-approved license for "
                f"{pkg.name}@{pkg.version}: {get_license_str(pkg)}\n"
                "Please update the package version on the TODO list.\n"
            )
        exit_code = 1

    for pkg, status in license_status.values():
        if status is False and pkg.name not in EXCEPTIONS_AND_TODOS:
            print(
                "We could not detect an OSI-approved license for "
                f"{pkg.name}@{pkg.version}: {get_license_str(pkg)}\n"
            )
            exit_code = 1
        if status is True and pkg.name in EXCEPTIONS:
            print(
                "Approved license detected for "
                f"{pkg.name}@{pkg.version}: {get_license_str(pkg)}\n"
                "Please remove the package from the EXCEPTIONS list.\n"
            )
            exit_code = 1

    for name in EXCEPTIONS_AND_TODOS.difference(license_status):
        print(
            f"Package {name} is tracked, but not used. "
            "Please remove it from the licenses.py file.\n"
        )
        exit_code = 1

    return exit_code


def check_license_status(package: PackageDefinition) -> bool:
    """Check if package licenses is OSI approved."""
    if package.license_expression:
        # Prefer 'License-Expression' if it exists
        return check_license_expression(package.license_expression) or False

    if (
        package.license_metadata
        and (check := check_license_expression(package.license_metadata)) is not None
    ):
        # Check license metadata if it's a valid SPDX license expression
        return check

    for approved_license in OSI_APPROVED_LICENSES:
        if approved_license in package.license:
            return True
    return False


def check_license_expression(license_str: str) -> bool | None:
    """Check if license expression is a valid and approved SPDX license string."""
    if license_str == "UNKNOWN" or "\n" in license_str:
        # Ignore common errors for license metadata values
        return None

    try:
        expr = licensing.parse(license_str, validate=True)
    except ExpressionError:
        return None
    return check_spdx_license(expr)


def check_spdx_license(expr: LicenseExpression) -> bool:
    """Check a SPDX license expression."""
    if isinstance(expr, LicenseSymbol):
        return expr.key in OSI_APPROVED_LICENSES_SPDX
    if isinstance(expr, OR):
        return any(check_spdx_license(arg) for arg in expr.args)
    if isinstance(expr, AND):
        return all(check_spdx_license(arg) for arg in expr.args)
    return False


def get_license_str(package: PackageDefinition) -> str:
    """Return license string."""
    return (
        f"{package.license_expression} -- {package.license_metadata} "
        f"-- {package.license_classifier}"
    )


def extract_licenses(args: ExtractArgs) -> int:
    """Extract license data for installed packages."""
    licenses = sorted(
        [get_package_metadata(dist) for dist in list(metadata.distributions())],
        key=lambda dist: dist["name"],
    )
    Path(args.output_file).write_text(json.dumps(licenses, indent=2))
    return 0


def get_package_metadata(dist: metadata.Distribution) -> PackageMetadata:
    """Get package metadata for distribution."""
    return {
        "name": dist.name,
        "version": dist.version,
        "license_expression": dist.metadata.get("License-Expression"),
        "license_metadata": dist.metadata.get("License"),
        "license_classifier": extract_license_classifier(
            dist.metadata.get_all("Classifier")
        ),
    }


def extract_license_classifier(classifiers: list[str] | None) -> list[str]:
    """Extract license from list of classifiers.

    E.g. 'License :: OSI Approved :: MIT License' -> 'MIT License'.
    Filter out bare 'License :: OSI Approved'.
    """
    return [
        license_classifier
        for classifier in classifiers or ()
        if classifier.startswith("License")
        and (license_classifier := classifier.rpartition(" :: ")[2])
        and license_classifier != "OSI Approved"
    ]


class ExtractArgs(Namespace):
    """Extract arguments."""

    output_file: str


class CheckArgs(Namespace):
    """Check arguments."""

    path: str


def main(argv: Sequence[str] | None = None) -> int:
    """Run the main script."""
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(title="Subcommands", required=True)

    parser_extract = subparsers.add_parser("extract")
    parser_extract.set_defaults(action="extract")
    parser_extract.add_argument(
        "--output-file",
        default="licenses.json",
        help="Path to store the licenses file",
    )

    parser_check = subparsers.add_parser("check")
    parser_check.set_defaults(action="check")
    parser_check.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        default="licenses.json",
        help="Path to json licenses file",
    )

    argv = argv or sys.argv[1:]
    args = parser.parse_args(argv)

    if args.action == "extract":
        args = cast(ExtractArgs, args)
        return extract_licenses(args)
    if args.action == "check":
        args = cast(CheckArgs, args)
        if (exit_code := check_licenses(args)) == 0:
            print("All licenses are approved!")
        return exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
