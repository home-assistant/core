#!/usr/bin/env python3
"""Home Assistant setup script."""
from datetime import datetime as dt
from setuptools import setup, find_packages

import homeassistant.const as hass_const

PROJECT_NAME = 'Home Assistant'
PROJECT_PACKAGE_NAME = 'homeassistant'
PROJECT_LICENSE = 'Apache License 2.0'
PROJECT_AUTHOR = 'The Home Assistant Authors'
PROJECT_COPYRIGHT = ' 2013-{}, {}'.format(dt.now().year, PROJECT_AUTHOR)
PROJECT_URL = 'https://home-assistant.io/'
PROJECT_EMAIL = 'hello@home-assistant.io'

PROJECT_GITHUB_USERNAME = 'home-assistant'
PROJECT_GITHUB_REPOSITORY = 'home-assistant'

PYPI_URL = 'https://pypi.python.org/pypi/{}'.format(PROJECT_PACKAGE_NAME)
GITHUB_PATH = '{}/{}'.format(
    PROJECT_GITHUB_USERNAME, PROJECT_GITHUB_REPOSITORY)
GITHUB_URL = 'https://github.com/{}'.format(GITHUB_PATH)

DOWNLOAD_URL = '{}/archive/{}.zip'.format(GITHUB_URL, hass_const.__version__)
PROJECT_URLS = {
    'Bug Reports': '{}/issues'.format(GITHUB_URL),
    'Dev Docs': 'https://developers.home-assistant.io/',
    'Discord': 'https://discordapp.com/invite/c5DvZ4e',
    'Forum': 'https://community.home-assistant.io/',
}

PACKAGES = find_packages(exclude=['tests', 'tests.*'])

REQUIRES = [
    'aiohttp==3.5.4',
    'astral==1.10.1',
    'async_timeout==3.0.1',
    'attrs==18.2.0',
    'bcrypt==3.1.6',
    'certifi>=2018.04.16',
    'jinja2>=2.10',
    'PyJWT==1.7.1',
    # PyJWT has loose dependency. We want the latest one.
    'cryptography==2.6.1',
    'pip>=8.0.3',
    'python-slugify==3.0.2',
    'pytz>=2019.01',
    'pyyaml>=3.13,<4',
    'requests==2.21.0',
    'ruamel.yaml==0.15.91',
    'voluptuous==0.11.5',
    'voluptuous-serialize==2.1.0',
]

MIN_PY_VERSION = '.'.join(map(str, hass_const.REQUIRED_PYTHON_VER))

setup(
    name=PROJECT_PACKAGE_NAME,
    version=hass_const.__version__,
    url=PROJECT_URL,
    download_url=DOWNLOAD_URL,
    project_urls=PROJECT_URLS,
    author=PROJECT_AUTHOR,
    author_email=PROJECT_EMAIL,
    packages=PACKAGES,
    include_package_data=True,
    zip_safe=False,
    install_requires=REQUIRES,
    python_requires='>={}'.format(MIN_PY_VERSION),
    test_suite='tests',
    entry_points={
        'console_scripts': [
            'hass = homeassistant.__main__:main'
        ]
    },
)
