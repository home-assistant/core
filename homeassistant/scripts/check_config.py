"""Script to ensure a configuration file exists."""
import argparse
import os
import glob
# from typing import Optional, Dict
from unittest.mock import patch
import importlib

import homeassistant.bootstrap as bootstrap
import homeassistant.config as config_util
import homeassistant.util.yaml as yaml_util
import homeassistant.loader as loader

REQUIREMENTS = ['yamllint>1,<2']


def run(args):
    """Handle ensure config commandline script."""
    parser = argparse.ArgumentParser(
        description=("Ensure a Home Assistant config exists, "
                     "creates one if necessary."))
    parser.add_argument(
        '-c', '--config',
        metavar='path_to_config_dir',
        default=config_util.get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")
    parser.add_argument(
        '--lint', default=False,
        help="Execute Yamllint")
    parser.add_argument(
        '--script',
        choices=['check_config'])

    args = parser.parse_args(args)

    config_dir = os.path.join(os.getcwd(), args.config)
    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        print('Config directory does not exist:', config_dir)
        return 1

    yaml_files = ['-c', os.path.splitext(__file__)[0] + '.yaml']
    yaml_files.extend(glob.glob(os.path.join(config_dir, '*.yaml')))
    # Python 3.5 gets a recursive, but not in 3.4
    yaml_files.extend(glob.glob(os.path.join(config_dir, '*/*.yaml')))

    if args.lint:
        _yaml_ordereddict(False)  # Does not like Ordereddicts
        import yamllint.cli
        yamllint.cli.run(yaml_files)

    # Normal loading
    config_path = config_util.ensure_config_exists(config_dir)
    print("Normal setup", config_path)
    _yaml_ordereddict(True)

    component_list = []

    # @patch("homeassistant.bootstrap._setup_component", return_value=True)
    # @patch("component.setup", return_value=True)

    patchers = []

    def cc_loader_get_component(comp_name):
        """A custom homeassistant.loader.get_component function.

        Follows similar logic to homeassistant.loader.get_component() to load
        the module and then fakes the setup(hass, config) method.

        potential_paths is required for the patching and not exposed in any
        way by the original method
        """
        potential_paths = ['custom_components.{}'.format(comp_name),
                           'homeassistant.components.{}'.format(comp_name)]
        for path in potential_paths:
            root_comp = path.rsplit(".", 1)[0] if '.' in comp_name else path
            if root_comp not in loader.AVAILABLE_COMPONENTS:
                continue
            try:
                module = importlib.import_module(path)
                if module.__spec__.origin == 'namespace':
                    continue

                # Patch it and return
                def fake_setup(hass, config):
                    """Fake setup, only record the component name."""
                    # pylint: disable=cell-var-from-loop
                    print('fake_setup:', path)
                    component_list.append(path)
                    # print('fake_setup:', path, str(config)[:80])
                    return True

                if hasattr(module, 'setup'):
                    patcher = patch(path + '.setup', side_effect=fake_setup)
                    patcher.start()
                    patchers.append(patcher)

                return module
            except ImportError:
                pass
        return False

    @patch("homeassistant.loader.get_component",
           side_effect=cc_loader_get_component)
    def load_all_the_config(*mocks):
        """Load the configs with appropriate patching."""
        print('mock start')
        bootstrap.from_config_file(config_path)
        print('Load complete')

        for mock in reversed(mocks):
            print(len(mock.call_args_list))

    load_all_the_config()

    return 0


def _yaml_ordereddict(enable):
    """Control patching of yaml for OrderedDicts."""
    import yaml
    from yaml import constructor
    # pylint: disable=protected-access
    yaml.SafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        yaml_util._ordered_dict if enable else
        constructor.SafeConstructor.construct_yaml_map)


# def test_setup_component(hass: core.HomeAssistant, domain: str,
#                          config: Optional[Dict]=None) -> bool:
#
#    print("setup domain:", domain)
#    return True
