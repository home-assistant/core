#!/usr/bin/env python3
"""Home Assistant setup script."""
from datetime import datetime as dt

from setuptools import find_packages, setup

PROJECT_NAME = "Home Assistant"
PROJECT_PACKAGE_NAME = "homeassistant"
PROJECT_LICENSE = "Apache License 2.0"
PROJECT_AUTHOR = "The Home Assistant Authors"
PROJECT_COPYRIGHT = f" 2013-{dt.now().year}, {PROJECT_AUTHOR}"
PROJECT_EMAIL = "hello@home-assistant.io"

PACKAGES = find_packages(exclude=["tests", "tests.*"])

setup(
    name=PROJECT_PACKAGE_NAME,
    author=PROJECT_AUTHOR,
    author_email=PROJECT_EMAIL,
    packages=PACKAGES,
    include_package_data=True,
    zip_safe=False,
    test_suite="tests",
    entry_points={"console_scripts": ["hass = homeassistant.__main__:main"]},
)
