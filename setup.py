#!/usr/bin/env python3
"""Home Assistant setup script."""
import os
from setuptools import setup, find_packages
from homeassistant.const import (__version__, PROJECT_PACKAGE_NAME,
                                 PROJECT_LICENSE, PROJECT_URL,
                                 PROJECT_EMAIL, PROJECT_DESCRIPTION,
                                 PROJECT_CLASSIFIERS, GITHUB_URL,
                                 PROJECT_AUTHOR)

HERE = os.path.abspath(os.path.dirname(__file__))
DOWNLOAD_URL = ('{}/archive/'
                '{}.zip'.format(GITHUB_URL, __version__))

PACKAGES = find_packages(exclude=['tests', 'tests.*'])

REQUIRES = [
    'requests==2.14.2',
    'pyyaml>=3.11,<4',
    'pytz>=2017.02',
    'pip>=7.1.0',
    'jinja2>=2.9.5',
    'voluptuous==0.10.5',
    'typing>=3,<4',
    'aiohttp==2.1.0',
    'async_timeout==1.2.1',
    'chardet==3.0.2',
    'astral==1.4',
]

setup(
    name=PROJECT_PACKAGE_NAME,
    version=__version__,
    license=PROJECT_LICENSE,
    url=PROJECT_URL,
    download_url=DOWNLOAD_URL,
    author=PROJECT_AUTHOR,
    author_email=PROJECT_EMAIL,
    description=PROJECT_DESCRIPTION,
    packages=PACKAGES,
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=REQUIRES,
    test_suite='tests',
    keywords=['home', 'automation'],
    entry_points={
        'console_scripts': [
            'hass = homeassistant.__main__:main'
        ]
    },
    classifiers=PROJECT_CLASSIFIERS,
)
