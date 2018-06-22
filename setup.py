#!/usr/bin/env python3
"""AIS dom setup script."""
from setuptools import setup, find_packages

import homeassistant.const as hass_const

PROJECT_NAME = 'AIS dom'
PROJECT_PACKAGE_NAME = 'ais-dom'
PROJECT_LICENSE = 'Apache License 2.0'
PROJECT_AUTHOR = 'Andrzej Raczkowski'
PROJECT_COPYRIGHT = ' 2018, {}'.format(PROJECT_AUTHOR)
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

PACKAGES = find_packages(exclude=['tests', 'tests.*'])

REQUIRES = [
    'aiohttp==3.2.1',
    'astral==1.6.1',
    'async_timeout==3.0.0',
    'attrs==18.1.0',
    'certifi>=2018.04.16',
    'jinja2>=2.10',
    'pip>=8.0.3',
    'pytz>=2018.04',
    'pyyaml>=3.11,<4',
    'requests==2.18.4',
    'typing>=3,<4',
    'voluptuous==0.11.1',
]

MIN_PY_VERSION = '.'.join(map(str, hass_const.REQUIRED_PYTHON_VER))

setup(
    name=PROJECT_PACKAGE_NAME,
    version=hass_const.__version__,
    license=PROJECT_LICENSE,
    url=PROJECT_URL,
    download_url=DOWNLOAD_URL,
    author=PROJECT_AUTHOR,
    author_email=PROJECT_EMAIL,
    description=PROJECT_DESCRIPTION,
    packages=PACKAGES,
    include_package_data=True,
    zip_safe=True,
    platforms='any',
    install_requires=REQUIRES,
    python_requires='>={}'.format(MIN_PY_VERSION),
    test_suite='tests',
    keywords=['home', 'automation'],
    entry_points={
        'console_scripts': [
            'hass = homeassistant.__main__:main'
        ]
    },
    classifiers=PROJECT_CLASSIFIERS,
)
