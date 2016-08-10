"""Script to ensure a configuration file exists."""
import argparse
import os
import re
from glob import glob
import logging
from typing import List
import pprint
from unittest.mock import patch
from textwrap import fill
from collections import OrderedDict

import homeassistant.bootstrap as bootstrap
import homeassistant.config as config_util
# import homeassistant.util.yaml as yaml_util
import homeassistant.loader as loader
import homeassistant.util.yaml as yaml

REQUIREMENTS = ['colorlog>2.1<3', 'colorama<=1']
SHOW_FILES = True
SHOW_SECRETS = True
SHOW_FULL_CONFIG = True
_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-locals,too-many-branches
def run(script_args: List) -> int:
    """Handle ensure config commandline script."""
    # Color support
    from colorama import init, Fore, Style
    init()

    def color(*args, c=Style.BRIGHT):  # pylint: disable=invalid-name
        """Color helper."""
        return c + ' '.join(args) + Style.RESET_ALL

    parser = argparse.ArgumentParser(
        description=("Check Home Assistant configuration."))
    parser.add_argument(
        '-c', '--config',
        # metavar='path_to_config_dir',
        default=config_util.get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")
    parser.add_argument(
        '--script', choices=['check_config'])
    parser.add_argument(
        '--verbose', default=False)

    args = parser.parse_args()

    config_dir = os.path.join(os.getcwd(), args.config)
    config_path = os.path.join(config_dir, 'configuration.yaml')
    if not os.path.isfile(config_path):
        print('Config does not exist:', config_path)
        return 1

    print(color("Testing configuration at", config_dir))

    res = check(config_path)

    if SHOW_FILES:  # Show Files
        print(color('yaml files'), '(used /',
              color('not used', c=Fore.RED)+')')
        # Python 3.5 gets a recursive, but not in 3.4
        for yfn in sorted(glob(os.path.join(config_dir, '*.yaml')) +
                          glob(os.path.join(config_dir, '*/*.yaml'))):
            the_color = '' if yfn in res['yaml_files'] else Fore.RED
            print(color('-', yfn, c=the_color))

    # pylint: disable=too-many-nested-blocks
    if SHOW_FULL_CONFIG:
        re_keys = re.compile(r"'([^']+)':")

        def indent(item, indent0, indent1):
            """Return indented text."""
            return re_keys.sub(color(r'\1')+':',
                               fill(pprint.pformat(item),
                                    initial_indent=indent0,
                                    subsequent_indent=indent1))

        def printlist(obj, level=0, pref=''):
            """Printlist."""
            indent1 = level * ' '
            indent0 = pref.rjust(level)
            if isinstance(obj, list):
                for ob0 in obj:
                    printlist(ob0, level+2, '- ')
            # elif isinstance(obj, dict):
            #    for key0, val0 in obj.items():
            #        printlist(val0, indent00 + key0 + ':' , indent1)
            else:
                print(indent(obj, indent0, indent1))

        components = deep_convert_dict(res['components'])
        for name, config in components:
            if config is None:
                continue
            print(color(name + ':'))
            printlist(config, 2, '')

    return 0


def check(config_path):
    """Perform a check by mocking hass load functions."""
    # List of components/platforms
    components = []
    yaml_files = {}
    secrets = {}

    original_get_component = loader.get_component
    original_load_yaml = yaml.load_yaml

    def mock_load_yaml(filename):
        """Mock hass.util.load_yaml to save config files."""
        yaml_files[filename] = True
        return original_load_yaml(filename)

    def mock_get_component(comp_name):
        """Mock hass.loader.get_component to replace setup & setup_platform."""
        def mock_setup(*kwargs):
            """Mock setup, only record the component name & config."""
            # pylint: disable=cell-var-from-loop
            components.append((comp_name, kwargs[1].get(comp_name)))
            return True

        module = original_get_component(comp_name)
        # Test if platform/component. Also: '.' in comp_name = platform
        if hasattr(module, 'setup'):
            module.setup = mock_setup
        if hasattr(module, 'setup_platform'):
            module.setup_platform = mock_setup

        module.setup_platform = mock_setup
        return module

    @patch("homeassistant.util.yaml.load_yaml",
           side_effect=mock_load_yaml)
    @patch("homeassistant.loader.get_component",
           side_effect=mock_get_component)
    def load_all_the_config(*mocks):
        """Load the configs with appropriate patching."""
        # Remove black & white logger, will be replace by hass logger
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        # Ensure we skip pip for speed
        bootstrap.from_config_file(config_path, skip_pip=True)

        _LOGGER.info('Load complete')

        for mock, func in zip(reversed(mocks), ['load_yaml', 'get_component']):
            if len(mock.call_args_list) == 0:
                _LOGGER.warning('Function %s never called', func)

    load_all_the_config()

    return {'yaml_files': yaml_files,
            'secrets': secrets,
            'components': components}


def deep_convert_dict(layer):
    """Convert an ordereddict to dict."""
    to_ret = layer
    if isinstance(layer, OrderedDict):
        to_ret = dict(layer)
    try:
        for key, value in to_ret.items():
            to_ret[key] = deep_convert_dict(value)
    except AttributeError:
        pass
    return to_ret
