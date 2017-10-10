"""Module to help with parsing and generating configuration files."""
import asyncio
from collections import OrderedDict
# pylint: disable=no-name-in-module
from distutils.version import LooseVersion  # pylint: disable=import-error
import logging
import os
import re
import shutil
import sys
# pylint: disable=unused-import
from typing import Any, List, Tuple  # NOQA

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_PACKAGES, CONF_UNIT_SYSTEM,
    CONF_TIME_ZONE, CONF_ELEVATION, CONF_UNIT_SYSTEM_METRIC,
    CONF_UNIT_SYSTEM_IMPERIAL, CONF_TEMPERATURE_UNIT, TEMP_CELSIUS,
    __version__, CONF_CUSTOMIZE, CONF_CUSTOMIZE_DOMAIN, CONF_CUSTOMIZE_GLOB,
    CONF_WHITELIST_EXTERNAL_DIRS)
from homeassistant.core import callback, DOMAIN as CONF_CORE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import get_component, get_platform
from homeassistant.util.yaml import load_yaml, SECRET_YAML
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as date_util, location as loc_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers import config_per_platform, extract_domain_configs

_LOGGER = logging.getLogger(__name__)

DATA_PERSISTENT_ERRORS = 'bootstrap_persistent_errors'
HA_COMPONENT_URL = '[{}](https://home-assistant.io/components/{}/)'
YAML_CONFIG_FILE = 'configuration.yaml'
VERSION_FILE = '.HA_VERSION'
CONFIG_DIR_NAME = '.homeassistant'
DATA_CUSTOMIZE = 'hass_customize'

FILE_MIGRATION = [
    ['ios.conf', '.ios.conf'],
]

DEFAULT_CORE_CONFIG = (
    # Tuples (attribute, default, auto detect property, description)
    (CONF_NAME, 'Home', None, 'Name of the location where Home Assistant is '
     'running'),
    (CONF_LATITUDE, 0, 'latitude', 'Location required to calculate the time'
     ' the sun rises and sets'),
    (CONF_LONGITUDE, 0, 'longitude', None),
    (CONF_ELEVATION, 0, None, 'Impacts weather/sunrise data'
                              ' (altitude above sea level in meters)'),
    (CONF_UNIT_SYSTEM, CONF_UNIT_SYSTEM_METRIC, None,
     '{} for Metric, {} for Imperial'.format(CONF_UNIT_SYSTEM_METRIC,
                                             CONF_UNIT_SYSTEM_IMPERIAL)),
    (CONF_TIME_ZONE, 'UTC', 'time_zone', 'Pick yours from here: http://en.wiki'
     'pedia.org/wiki/List_of_tz_database_time_zones'),
    (CONF_CUSTOMIZE, '!include customize.yaml', None, 'Customization file'),
)  # type: Tuple[Tuple[str, Any, Any, str], ...]
DEFAULT_CONFIG = """
# Show links to resources in log and frontend
introduction:

# Enables the frontend
frontend:

# Enables configuration UI
config:

http:
  # Secrets are defined in the file secrets.yaml
  # api_password: !secret http_password
  # Uncomment this if you are using SSL/TLS, running in Docker container, etc.
  # base_url: example.duckdns.org:8123

# Checks for available updates
# Note: This component will send some information about your system to
# the developers to assist with development of Home Assistant.
# For more information, please see:
# https://home-assistant.io/blog/2016/10/25/explaining-the-updater/
updater:
  # Optional, allows Home Assistant developers to focus on popular components.
  # include_used_components: true

# Discover some devices automatically
discovery:

# Allows you to issue voice commands from the frontend in enabled browsers
conversation:

# Enables support for tracking state changes over time
history:

# View all events in a logbook
logbook:

# Track the sun
sun:

# Weather prediction
sensor:
  - platform: yr

# Text to speech
tts:
  - platform: google

group: !include groups.yaml
automation: !include automations.yaml
script: !include scripts.yaml
"""
DEFAULT_SECRETS = """
# Use this file to store secrets like usernames and passwords.
# Learn more at https://home-assistant.io/docs/configuration/secrets/
http_password: welcome
"""


PACKAGES_CONFIG_SCHEMA = vol.Schema({
    cv.slug: vol.Schema(  # Package names are slugs
        {cv.slug: vol.Any(dict, list)})  # Only slugs for component names
})

CUSTOMIZE_CONFIG_SCHEMA = vol.Schema({
    vol.Optional(CONF_CUSTOMIZE, default={}):
        vol.Schema({cv.entity_id: dict}),
    vol.Optional(CONF_CUSTOMIZE_DOMAIN, default={}):
        vol.Schema({cv.string: dict}),
    vol.Optional(CONF_CUSTOMIZE_GLOB, default={}):
        vol.Schema({cv.string: OrderedDict}),
})

CORE_CONFIG_SCHEMA = CUSTOMIZE_CONFIG_SCHEMA.extend({
    CONF_NAME: vol.Coerce(str),
    CONF_LATITUDE: cv.latitude,
    CONF_LONGITUDE: cv.longitude,
    CONF_ELEVATION: vol.Coerce(int),
    vol.Optional(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
    CONF_UNIT_SYSTEM: cv.unit_system,
    CONF_TIME_ZONE: cv.time_zone,
    vol.Optional(CONF_WHITELIST_EXTERNAL_DIRS):
        # pylint: disable=no-value-for-parameter
        vol.All(cv.ensure_list, [vol.IsDir()]),
    vol.Optional(CONF_PACKAGES, default={}): PACKAGES_CONFIG_SCHEMA,
})


def get_default_config_dir() -> str:
    """Put together the default configuration directory based on the OS."""
    data_dir = os.getenv('APPDATA') if os.name == "nt" \
        else os.path.expanduser('~')
    return os.path.join(data_dir, CONFIG_DIR_NAME)


def ensure_config_exists(config_dir: str, detect_location: bool=True) -> str:
    """Ensure a configuration file exists in given configuration directory.

    Creating a default one if needed.
    Return path to the configuration file.
    """
    config_path = find_config_file(config_dir)

    if config_path is None:
        print("Unable to find configuration. Creating default one in",
              config_dir)
        config_path = create_default_config(config_dir, detect_location)

    return config_path


def create_default_config(config_dir, detect_location=True):
    """Create a default configuration file in given configuration directory.

    Return path to new config file if success, None if failed.
    This method needs to run in an executor.
    """
    from homeassistant.components.config.group import (
        CONFIG_PATH as GROUP_CONFIG_PATH)
    from homeassistant.components.config.automation import (
        CONFIG_PATH as AUTOMATION_CONFIG_PATH)
    from homeassistant.components.config.script import (
        CONFIG_PATH as SCRIPT_CONFIG_PATH)
    from homeassistant.components.config.customize import (
        CONFIG_PATH as CUSTOMIZE_CONFIG_PATH)

    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)
    secret_path = os.path.join(config_dir, SECRET_YAML)
    version_path = os.path.join(config_dir, VERSION_FILE)
    group_yaml_path = os.path.join(config_dir, GROUP_CONFIG_PATH)
    automation_yaml_path = os.path.join(config_dir, AUTOMATION_CONFIG_PATH)
    script_yaml_path = os.path.join(config_dir, SCRIPT_CONFIG_PATH)
    customize_yaml_path = os.path.join(config_dir, CUSTOMIZE_CONFIG_PATH)

    info = {attr: default for attr, default, _, _ in DEFAULT_CORE_CONFIG}

    location_info = detect_location and loc_util.detect_location_info()

    if location_info:
        if location_info.use_metric:
            info[CONF_UNIT_SYSTEM] = CONF_UNIT_SYSTEM_METRIC
        else:
            info[CONF_UNIT_SYSTEM] = CONF_UNIT_SYSTEM_IMPERIAL

        for attr, default, prop, _ in DEFAULT_CORE_CONFIG:
            if prop is None:
                continue
            info[attr] = getattr(location_info, prop) or default

        if location_info.latitude and location_info.longitude:
            info[CONF_ELEVATION] = loc_util.elevation(
                location_info.latitude, location_info.longitude)

    # Writing files with YAML does not create the most human readable results
    # So we're hard coding a YAML template.
    try:
        with open(config_path, 'wt') as config_file:
            config_file.write("homeassistant:\n")

            for attr, _, _, description in DEFAULT_CORE_CONFIG:
                if info[attr] is None:
                    continue
                elif description:
                    config_file.write("  # {}\n".format(description))
                config_file.write("  {}: {}\n".format(attr, info[attr]))

            config_file.write(DEFAULT_CONFIG)

        with open(secret_path, 'wt') as secret_file:
            secret_file.write(DEFAULT_SECRETS)

        with open(version_path, 'wt') as version_file:
            version_file.write(__version__)

        with open(group_yaml_path, 'wt'):
            pass

        with open(automation_yaml_path, 'wt') as fil:
            fil.write('[]')

        with open(script_yaml_path, 'wt'):
            pass

        with open(customize_yaml_path, 'wt'):
            pass

        return config_path

    except IOError:
        print("Unable to create default configuration file", config_path)
        return None


@asyncio.coroutine
def async_hass_config_yaml(hass):
    """Load YAML from a Home Assistant configuration file.

    This function allow a component inside the asyncio loop to reload its
    configuration by itself.

    This method is a coroutine.
    """
    def _load_hass_yaml_config():
        path = find_config_file(hass.config.config_dir)
        conf = load_yaml_config_file(path)
        return conf

    conf = yield from hass.async_add_job(_load_hass_yaml_config)
    return conf


def find_config_file(config_dir):
    """Look in given directory for supported configuration files.

    Async friendly.
    """
    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)

    return config_path if os.path.isfile(config_path) else None


def load_yaml_config_file(config_path):
    """Parse a YAML configuration file.

    This method needs to run in an executor.
    """
    try:
        conf_dict = load_yaml(config_path)
    except FileNotFoundError as err:
        raise HomeAssistantError("Config file not found: {}".format(
            getattr(err, 'filename', err)))

    if not isinstance(conf_dict, dict):
        msg = "The configuration file {} does not contain a dictionary".format(
            os.path.basename(config_path))
        _LOGGER.error(msg)
        raise HomeAssistantError(msg)

    return conf_dict


def process_ha_config_upgrade(hass):
    """Upgrade configuration if necessary.

    This method needs to run in an executor.
    """
    version_path = hass.config.path(VERSION_FILE)

    try:
        with open(version_path, 'rt') as inp:
            conf_version = inp.readline().strip()
    except FileNotFoundError:
        # Last version to not have this file
        conf_version = '0.7.7'

    if conf_version == __version__:
        return

    _LOGGER.info("Upgrading configuration directory from %s to %s",
                 conf_version, __version__)

    if LooseVersion(conf_version) < LooseVersion('0.50'):
        # 0.50 introduced persistent deps dir.
        lib_path = hass.config.path('deps')
        if os.path.isdir(lib_path):
            shutil.rmtree(lib_path)

    with open(version_path, 'wt') as outp:
        outp.write(__version__)

    _LOGGER.info("Migrating old system configuration files to new locations")
    for oldf, newf in FILE_MIGRATION:
        if os.path.isfile(hass.config.path(oldf)):
            _LOGGER.info("Migrating %s to %s", oldf, newf)
            os.rename(hass.config.path(oldf), hass.config.path(newf))


@callback
def async_log_exception(ex, domain, config, hass):
    """Generate log exception for configuration validation.

    This method must be run in the event loop.
    """
    message = "Invalid config for [{}]: ".format(domain)
    if hass is not None:
        async_notify_setup_error(hass, domain, True)

    if 'extra keys not allowed' in ex.error_message:
        message += '[{}] is an invalid option for [{}]. Check: {}->{}.'\
                   .format(ex.path[-1], domain, domain,
                           '->'.join(str(m) for m in ex.path))
    else:
        message += '{}.'.format(humanize_error(config, ex))

    domain_config = config.get(domain, config)
    message += " (See {}, line {}). ".format(
        getattr(domain_config, '__config_file__', '?'),
        getattr(domain_config, '__line__', '?'))

    if domain != 'homeassistant':
        message += ('Please check the docs at '
                    'https://home-assistant.io/components/{}/'.format(domain))

    _LOGGER.error(message)


@asyncio.coroutine
def async_process_ha_core_config(hass, config):
    """Process the [homeassistant] section from the configuration.

    This method is a coroutine.
    """
    config = CORE_CONFIG_SCHEMA(config)
    hac = hass.config

    def set_time_zone(time_zone_str):
        """Help to set the time zone."""
        if time_zone_str is None:
            return

        time_zone = date_util.get_time_zone(time_zone_str)

        if time_zone:
            hac.time_zone = time_zone
            date_util.set_default_time_zone(time_zone)
        else:
            _LOGGER.error("Received invalid time zone %s", time_zone_str)

    for key, attr in ((CONF_LATITUDE, 'latitude'),
                      (CONF_LONGITUDE, 'longitude'),
                      (CONF_NAME, 'location_name'),
                      (CONF_ELEVATION, 'elevation')):
        if key in config:
            setattr(hac, attr, config[key])

    if CONF_TIME_ZONE in config:
        set_time_zone(config.get(CONF_TIME_ZONE))

    # Init whitelist external dir
    hac.whitelist_external_dirs = set((hass.config.path('www'),))
    if CONF_WHITELIST_EXTERNAL_DIRS in config:
        hac.whitelist_external_dirs.update(
            set(config[CONF_WHITELIST_EXTERNAL_DIRS]))

    # Customize
    cust_exact = dict(config[CONF_CUSTOMIZE])
    cust_domain = dict(config[CONF_CUSTOMIZE_DOMAIN])
    cust_glob = OrderedDict(config[CONF_CUSTOMIZE_GLOB])

    for name, pkg in config[CONF_PACKAGES].items():
        pkg_cust = pkg.get(CONF_CORE)

        if pkg_cust is None:
            continue

        try:
            pkg_cust = CUSTOMIZE_CONFIG_SCHEMA(pkg_cust)
        except vol.Invalid:
            _LOGGER.warning("Package %s contains invalid customize", name)
            continue

        cust_exact.update(pkg_cust[CONF_CUSTOMIZE])
        cust_domain.update(pkg_cust[CONF_CUSTOMIZE_DOMAIN])
        cust_glob.update(pkg_cust[CONF_CUSTOMIZE_GLOB])

    hass.data[DATA_CUSTOMIZE] = \
        EntityValues(cust_exact, cust_domain, cust_glob)

    if CONF_UNIT_SYSTEM in config:
        if config[CONF_UNIT_SYSTEM] == CONF_UNIT_SYSTEM_IMPERIAL:
            hac.units = IMPERIAL_SYSTEM
        else:
            hac.units = METRIC_SYSTEM
    elif CONF_TEMPERATURE_UNIT in config:
        unit = config[CONF_TEMPERATURE_UNIT]
        if unit == TEMP_CELSIUS:
            hac.units = METRIC_SYSTEM
        else:
            hac.units = IMPERIAL_SYSTEM
        _LOGGER.warning("Found deprecated temperature unit in core "
                        "configuration expected unit system. Replace '%s: %s' "
                        "with '%s: %s'", CONF_TEMPERATURE_UNIT, unit,
                        CONF_UNIT_SYSTEM, hac.units.name)

    # Shortcut if no auto-detection necessary
    if None not in (hac.latitude, hac.longitude, hac.units,
                    hac.time_zone, hac.elevation):
        return

    discovered = []

    # If we miss some of the needed values, auto detect them
    if None in (hac.latitude, hac.longitude, hac.units,
                hac.time_zone):
        info = yield from hass.async_add_job(
            loc_util.detect_location_info)

        if info is None:
            _LOGGER.error("Could not detect location information")
            return

        if hac.latitude is None and hac.longitude is None:
            hac.latitude, hac.longitude = (info.latitude, info.longitude)
            discovered.append(('latitude', hac.latitude))
            discovered.append(('longitude', hac.longitude))

        if hac.units is None:
            hac.units = METRIC_SYSTEM if info.use_metric else IMPERIAL_SYSTEM
            discovered.append((CONF_UNIT_SYSTEM, hac.units.name))

        if hac.location_name is None:
            hac.location_name = info.city
            discovered.append(('name', info.city))

        if hac.time_zone is None:
            set_time_zone(info.time_zone)
            discovered.append(('time_zone', info.time_zone))

    if hac.elevation is None and hac.latitude is not None and \
       hac.longitude is not None:
        elevation = yield from hass.async_add_job(
            loc_util.elevation, hac.latitude, hac.longitude)
        hac.elevation = elevation
        discovered.append(('elevation', elevation))

    if discovered:
        _LOGGER.warning(
            "Incomplete core configuration. Auto detected %s",
            ", ".join('{}: {}'.format(key, val) for key, val in discovered))


def _log_pkg_error(package, component, config, message):
    """Log an error while merging."""
    message = "Package {} setup failed. Component {} {}".format(
        package, component, message)

    pack_config = config[CONF_CORE][CONF_PACKAGES].get(package, config)
    message += " (See {}:{}). ".format(
        getattr(pack_config, '__config_file__', '?'),
        getattr(pack_config, '__line__', '?'))

    _LOGGER.error(message)


def _identify_config_schema(module):
    """Extract the schema and identify list or dict based."""
    try:
        schema = module.CONFIG_SCHEMA.schema[module.DOMAIN]
    except (AttributeError, KeyError):
        return (None, None)
    t_schema = str(schema)
    if t_schema.startswith('{'):
        return ('dict', schema)
    if t_schema.startswith(('[', 'All(<function ensure_list')):
        return ('list', schema)
    return '', schema


def merge_packages_config(config, packages):
    """Merge packages into the top-level configuration. Mutate config."""
    # pylint: disable=too-many-nested-blocks
    PACKAGES_CONFIG_SCHEMA(packages)
    for pack_name, pack_conf in packages.items():
        for comp_name, comp_conf in pack_conf.items():
            if comp_name == CONF_CORE:
                continue
            component = get_component(comp_name)

            if component is None:
                _log_pkg_error(pack_name, comp_name, config, "does not exist")
                continue

            if hasattr(component, 'PLATFORM_SCHEMA'):
                config[comp_name] = cv.ensure_list(config.get(comp_name))
                config[comp_name].extend(cv.ensure_list(comp_conf))
                continue

            if hasattr(component, 'CONFIG_SCHEMA'):
                merge_type, _ = _identify_config_schema(component)

                if merge_type == 'list':
                    config[comp_name] = cv.ensure_list(config.get(comp_name))
                    config[comp_name].extend(cv.ensure_list(comp_conf))
                    continue

                if merge_type == 'dict':
                    if not isinstance(comp_conf, dict):
                        _log_pkg_error(
                            pack_name, comp_name, config,
                            "cannot be merged. Expected a dict.")
                        continue

                    if comp_name not in config:
                        config[comp_name] = OrderedDict()

                    if not isinstance(config[comp_name], dict):
                        _log_pkg_error(
                            pack_name, comp_name, config,
                            "cannot be merged. Dict expected in main config.")
                        continue

                    for key, val in comp_conf.items():
                        if key in config[comp_name]:
                            _log_pkg_error(pack_name, comp_name, config,
                                           "duplicate key '{}'".format(key))
                            continue
                        config[comp_name][key] = val
                    continue

            # The last merge type are sections that may occur only once
            if comp_name in config:
                _log_pkg_error(
                    pack_name, comp_name, config, "may occur only once"
                    " and it already exist in your main configuration")
                continue
            config[comp_name] = comp_conf

    return config


@callback
def async_process_component_config(hass, config, domain):
    """Check component configuration and return processed configuration.

    Raise a vol.Invalid exception on error.

    This method must be run in the event loop.
    """
    component = get_component(domain)

    if hasattr(component, 'CONFIG_SCHEMA'):
        try:
            config = component.CONFIG_SCHEMA(config)
        except vol.Invalid as ex:
            async_log_exception(ex, domain, config, hass)
            return None

    elif hasattr(component, 'PLATFORM_SCHEMA'):
        platforms = []
        for p_name, p_config in config_per_platform(config, domain):
            # Validate component specific platform schema
            try:
                p_validated = component.PLATFORM_SCHEMA(p_config)
            except vol.Invalid as ex:
                async_log_exception(ex, domain, config, hass)
                continue

            # Not all platform components follow same pattern for platforms
            # So if p_name is None we are not going to validate platform
            # (the automation component is one of them)
            if p_name is None:
                platforms.append(p_validated)
                continue

            platform = get_platform(domain, p_name)

            if platform is None:
                continue

            # Validate platform specific schema
            if hasattr(platform, 'PLATFORM_SCHEMA'):
                # pylint: disable=no-member
                try:
                    p_validated = platform.PLATFORM_SCHEMA(p_validated)
                except vol.Invalid as ex:
                    async_log_exception(ex, '{}.{}'.format(domain, p_name),
                                        p_validated, hass)
                    continue

            platforms.append(p_validated)

        # Create a copy of the configuration with all config for current
        # component removed and add validated config back in.
        filter_keys = extract_domain_configs(config, domain)
        config = {key: value for key, value in config.items()
                  if key not in filter_keys}
        config[domain] = platforms

    return config


@asyncio.coroutine
def async_check_ha_config_file(hass):
    """Check if Home Assistant configuration file is valid.

    This method is a coroutine.
    """
    proc = yield from asyncio.create_subprocess_exec(
        sys.executable, '-m', 'homeassistant', '--script',
        'check_config', '--config', hass.config.config_dir,
        stdout=asyncio.subprocess.PIPE, loop=hass.loop)
    # Wait for the subprocess exit
    stdout_data, dummy = yield from proc.communicate()
    result = yield from proc.wait()

    if not result:
        return None

    return re.sub(r'\033\[[^m]*m', '', str(stdout_data, 'utf-8'))


@callback
def async_notify_setup_error(hass, component, link=False):
    """Print a persistent notification.

    This method must be run in the event loop.
    """
    from homeassistant.components import persistent_notification

    errors = hass.data.get(DATA_PERSISTENT_ERRORS)

    if errors is None:
        errors = hass.data[DATA_PERSISTENT_ERRORS] = {}

    errors[component] = errors.get(component) or link
    _lst = [HA_COMPONENT_URL.format(name.replace('_', '-'), name)
            if link else name for name, link in errors.items()]
    message = ('The following components and platforms could not be set up:\n'
               '* ' + '\n* '.join(list(_lst)) + '\nPlease check your config')
    persistent_notification.async_create(
        hass, message, 'Invalid config', 'invalid_config')
