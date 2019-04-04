#!/usr/bin/env python3
"""AIS dom setup script."""
from datetime import datetime as dt
from setuptools import setup, find_packages

import homeassistant.const as hass_const

PROJECT_NAME = 'AIS dom'
PROJECT_PACKAGE_NAME = 'ais-dom'
PROJECT_LICENSE = 'Apache License 2.0'
PROJECT_AUTHOR = 'Andrzej Raczkowski'
PROJECT_COPYRIGHT = ' 2016-{}, {}'.format(dt.now().year, PROJECT_AUTHOR)
PROJECT_URL = 'https://ai-speaker.com/'
PROJECT_EMAIL = 'info@sviete.pl'
PROJECT_DESCRIPTION = ('IOT hub and automation platform for AI-Spekaer.com'
                       ' running on Home Assistant.')

PROJECT_CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: End Users/Desktop',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Topic :: Home Automation'
]

PYPI_URL = 'https://pypi.python.org/pypi/{}'.format(PROJECT_PACKAGE_NAME)
GITHUB_URL = 'https://github.com/sviete/home-assistant'

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
    'PyJWT==1.6.4',
    # PyJWT has loose dependency. We want the latest one.
    'cryptography==2.5',
    'pip>=8.0.3',
    'python-slugify==1.2.6',
    'pytz>=2018.07',
    'pyyaml>=3.13,<4',
    'requests==2.21.0',
    'ruamel.yaml==0.15.89',
    'voluptuous==0.11.5',
    'voluptuous-serialize==2.1.0', 'markdown', 'pyqrcode', 'gmusicapi'
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
