#!/usr/bin/env python3
"""Generate an updated requirements_all.txt."""
import fnmatch
import importlib
import os
import pathlib
import pkgutil
import re
import sys

from script.hassfest.model import Integration

COMMENT_REQUIREMENTS = (
    'Adafruit-DHT',
    'Adafruit_BBIO',
    'avion',
    'beacontools',
    'blinkt',
    'bluepy',
    'bme680',
    'credstash',
    'decora',
    'envirophat',
    'evdev',
    'face_recognition',
    'fritzconnection',
    'i2csense',
    'opencv-python',
    'py_noaa',
    'VL53L1X2',
    'pybluez',
    'pycups',
    'PySwitchbot',
    'pySwitchmate',
    'python-eq3bt',
    'python-lirc',
    'pyuserinput',
    'raspihats',
    'rpi-rf',
    'RPi.GPIO',
    'smbus-cffi',
)

TEST_REQUIREMENTS = (
    'ambiclimate',
    'aioambient',
    'aioautomatic',
    'aiobotocore',
    'aiohttp_cors',
    'aiohue',
    'aiounifi',
    'aioswitcher',
    'apns2',
    'av',
    'axis',
    'caldav',
    'coinmarketcap',
    'defusedxml',
    'dsmr_parser',
    'eebrightbox',
    'emulated_roku',
    'enocean',
    'ephem',
    'evohomeclient',
    'feedparser-homeassistant',
    'foobot_async',
    'geojson_client',
    'georss_generic_client',
    'georss_ign_sismologia_client',
    'google-api-python-client',
    'gTTS-token',
    'ha-ffmpeg',
    'hangups',
    'HAP-python',
    'hass-nabucasa',
    'haversine',
    'hbmqtt',
    'hdate',
    'holidays',
    'home-assistant-frontend',
    'homekit[IP]',
    'homematicip',
    'httplib2',
    'influxdb',
    'jsonpath',
    'libpurecool',
    'libsoundtouch',
    'luftdaten',
    'mbddns',
    'mficlient',
    'numpy',
    'oauth2client',
    'paho-mqtt',
    'pexpect',
    'pilight',
    'pmsensor',
    'prometheus_client',
    'ptvsd',
    'pushbullet.py',
    'py-canary',
    'pyblackbird',
    'pydeconz',
    'pydispatcher',
    'pyheos',
    'pyhomematic',
    'pylitejet',
    'pymonoprice',
    'pynx584',
    'pyopenuv',
    'pyotp',
    'pyps4-homeassistant',
    'pysmartapp',
    'pysmartthings',
    'pysonos',
    'pyqwikswitch',
    'PyRMVtransport',
    'PyTransportNSW',
    'pyspcwebgw',
    'python-forecastio',
    'python-nest',
    'python_awair',
    'pytradfri[async]',
    'pyunifi',
    'pyupnp-async',
    'pywebpush',
    'pyHS100',
    'PyNaCl',
    'regenmaschine',
    'restrictedpython',
    'rflink',
    'ring_doorbell',
    'rxv',
    'simplisafe-python',
    'sleepyq',
    'smhi-pkg',
    'somecomfort',
    'sqlalchemy',
    'srpenergy',
    'statsd',
    'toonapilib',
    'uvcclient',
    'vsure',
    'warrant',
    'pythonwhois',
    'wakeonlan',
    'vultr',
    'YesssSMS',
    'ruamel.yaml',
    'zigpy-homeassistant',
    'bellows-homeassistant',
)

IGNORE_PACKAGES = (
    'homeassistant.components.hangouts.hangups_utils',
    'homeassistant.components.cloud.client',
    'homeassistant.components.homekit.*',
    'homeassistant.components.recorder.models',
)

IGNORE_PIN = ('colorlog>2.1,<3', 'keyring>=9.3,<10.0', 'urllib3')

IGNORE_REQ = (
    'colorama<=1',  # Windows only requirement in check_config
)

URL_PIN = ('https://developers.home-assistant.io/docs/'
           'creating_platform_code_review.html#1-requirements')


CONSTRAINT_PATH = os.path.join(os.path.dirname(__file__),
                               '../homeassistant/package_constraints.txt')
CONSTRAINT_BASE = """
pycryptodome>=3.6.6

# Breaks Python 3.6 and is not needed for our supported Python versions
enum34==1000000000.0.0

# This is a old unmaintained library and is replaced with pycryptodome
pycrypto==1000000000.0.0

# Contains code to modify Home Assistant to work around our rules
python-systemair-savecair==1000000000.0.0

# Newer version causes pylint to take forever
# https://github.com/timothycrosley/isort/issues/848
isort==4.3.4
"""


def explore_module(package, explore_children):
    """Explore the modules."""
    module = importlib.import_module(package)

    found = []

    if not hasattr(module, '__path__'):
        return found

    for _, name, _ in pkgutil.iter_modules(module.__path__, package + '.'):
        found.append(name)

        if explore_children:
            found.extend(explore_module(name, False))

    return found


def core_requirements():
    """Gather core requirements out of setup.py."""
    with open('setup.py') as inp:
        reqs_raw = re.search(
            r'REQUIRES = \[(.*?)\]', inp.read(), re.S).group(1)
    return re.findall(r"'(.*?)'", reqs_raw)


def comment_requirement(req):
    """Comment out requirement. Some don't install on all systems."""
    return any(ign in req for ign in COMMENT_REQUIREMENTS)


def gather_modules():
    """Collect the information."""
    reqs = {}

    errors = []

    gather_requirements_from_manifests(errors, reqs)
    gather_requirements_from_modules(errors, reqs)

    for key in reqs:
        reqs[key] = sorted(reqs[key],
                           key=lambda name: (len(name.split('.')), name))

    if errors:
        print("******* ERROR")
        print("Errors while importing: ", ', '.join(errors))
        return None

    return reqs


def gather_requirements_from_manifests(errors, reqs):
    """Gather all of the requirements from manifests."""
    integrations = Integration.load_dir(pathlib.Path(
        'homeassistant/components'
    ))
    for domain in sorted(integrations):
        integration = integrations[domain]

        if not integration.manifest:
            errors.append(
                'The manifest for component {} is invalid.'.format(domain)
            )
            continue

        process_requirements(
            errors,
            integration.manifest['requirements'],
            'homeassistant.components.{}'.format(domain),
            reqs
        )


def gather_requirements_from_modules(errors, reqs):
    """Collect the requirements from the modules directly."""
    for package in sorted(
            explore_module('homeassistant.scripts', True) +
            explore_module('homeassistant.auth', True)):
        try:
            module = importlib.import_module(package)
        except ImportError as err:
            for pattern in IGNORE_PACKAGES:
                if fnmatch.fnmatch(package, pattern):
                    break
            else:
                print("{}: {}".format(package.replace('.', '/') + '.py', err))
                errors.append(package)
            continue

        if getattr(module, 'REQUIREMENTS', None):
            process_requirements(errors, module.REQUIREMENTS, package, reqs)


def process_requirements(errors, module_requirements, package, reqs):
    """Process all of the requirements."""
    for req in module_requirements:
        if req in IGNORE_REQ:
            continue
        if '://' in req:
            errors.append(
                "{}[Only pypi dependencies are allowed: {}]".format(
                    package, req))
        if req.partition('==')[1] == '' and req not in IGNORE_PIN:
            errors.append(
                "{}[Please pin requirement {}, see {}]".format(
                    package, req, URL_PIN))
        reqs.setdefault(req, []).append(package)


def generate_requirements_list(reqs):
    """Generate a pip file based on requirements."""
    output = []
    for pkg, requirements in sorted(reqs.items(), key=lambda item: item[0]):
        for req in sorted(requirements):
            output.append('\n# {}'.format(req))

        if comment_requirement(pkg):
            output.append('\n# {}\n'.format(pkg))
        else:
            output.append('\n{}\n'.format(pkg))
    return ''.join(output)


def requirements_all_output(reqs):
    """Generate output for requirements_all."""
    output = []
    output.append('# Home Assistant core')
    output.append('\n')
    output.append('\n'.join(core_requirements()))
    output.append('\n')
    output.append(generate_requirements_list(reqs))

    return ''.join(output)


def requirements_test_output(reqs):
    """Generate output for test_requirements."""
    output = []
    output.append('# Home Assistant test')
    output.append('\n')
    with open('requirements_test.txt') as test_file:
        output.append(test_file.read())
    output.append('\n')
    filtered = {key: value for key, value in reqs.items()
                if any(
                    re.search(r'(^|#){}($|[=><])'.format(re.escape(ign)),
                              key) is not None for ign in TEST_REQUIREMENTS)}
    output.append(generate_requirements_list(filtered))

    return ''.join(output)


def gather_constraints():
    """Construct output for constraint file."""
    return '\n'.join(core_requirements() + [''])


def write_requirements_file(data):
    """Write the modules to the requirements_all.txt."""
    with open('requirements_all.txt', 'w+', newline="\n") as req_file:
        req_file.write(data)


def write_test_requirements_file(data):
    """Write the modules to the requirements_test_all.txt."""
    with open('requirements_test_all.txt', 'w+', newline="\n") as req_file:
        req_file.write(data)


def write_constraints_file(data):
    """Write constraints to a file."""
    with open(CONSTRAINT_PATH, 'w+', newline="\n") as req_file:
        req_file.write(data + CONSTRAINT_BASE)


def validate_requirements_file(data):
    """Validate if requirements_all.txt is up to date."""
    with open('requirements_all.txt', 'r') as req_file:
        return data == req_file.read()


def validate_requirements_test_file(data):
    """Validate if requirements_test_all.txt is up to date."""
    with open('requirements_test_all.txt', 'r') as req_file:
        return data == req_file.read()


def validate_constraints_file(data):
    """Validate if constraints is up to date."""
    with open(CONSTRAINT_PATH, 'r') as req_file:
        return data + CONSTRAINT_BASE == req_file.read()


def main(validate):
    """Run the script."""
    if not os.path.isfile('requirements_all.txt'):
        print('Run this from HA root dir')
        return 1

    data = gather_modules()

    if data is None:
        return 1

    constraints = gather_constraints()

    reqs_file = requirements_all_output(data)
    reqs_test_file = requirements_test_output(data)

    if validate:
        errors = []
        if not validate_requirements_file(reqs_file):
            errors.append("requirements_all.txt is not up to date")

        if not validate_requirements_test_file(reqs_test_file):
            errors.append("requirements_test_all.txt is not up to date")

        if not validate_constraints_file(constraints):
            errors.append(
                "home-assistant/package_constraints.txt is not up to date")

        if errors:
            print("******* ERROR")
            print('\n'.join(errors))
            print("Please run script/gen_requirements_all.py")
            return 1

        return 0

    write_requirements_file(reqs_file)
    write_test_requirements_file(reqs_test_file)
    write_constraints_file(constraints)
    return 0


if __name__ == '__main__':
    _VAL = sys.argv[-1] == 'validate'
    sys.exit(main(_VAL))
