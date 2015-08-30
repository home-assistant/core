import os
import re
from setuptools import setup, find_packages

PACKAGE_NAME = 'homeassistant'
HERE = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(HERE, PACKAGE_NAME, 'const.py')) as fp:
    VERSION = re.search("__version__ = ['\"]([^']+)['\"]\n", fp.read()).group(1)
DOWNLOAD_URL = \
    'https://github.com/balloob/home-assistant/archive/{}.zip'.format(VERSION)

PACKAGES = find_packages() + \
    ['homeassistant.external', 'homeassistant.external.noop',
     'homeassistant.external.nzbclients', 'homeassistant.external.vera']

PACKAGE_DATA = \
    {'homeassistant.components.frontend': ['index.html.template'],
     'homeassistant.components.frontend.www_static': ['*.*'],
     'homeassistant.components.frontend.www_static.images': ['*.*']}

REQUIRES = \
    [line.strip() for line in open('requirements.txt', 'r')]

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    license='MIT License',
    url='https://home-assistant.io/',
    download_url=DOWNLOAD_URL,
    author='Paulus Schoutsen',
    author_email='paulus@paulusschoutsen.nl',
    description='Open-source home automation platform running on Python 3.',
    packages=PACKAGES,
    include_package_data=True,
    package_data=PACKAGE_DATA,
    zip_safe=False,
    platforms='any',
    install_requires=REQUIRES,
    keywords=['home', 'automation'],
    entry_points={
        'console_scripts': [
            'hass = homeassistant.__main__:main'
        ]
    },
    classifiers=[
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.4',
        'Topic :: Home Automation'
    ]
)
