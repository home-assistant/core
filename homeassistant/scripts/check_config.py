"""Script to ensure a configuration file exists."""
import argparse
import os
import sys
import glob

import homeassistant.config as config_util
import homeassistant.util.package as pkg_util

DEPENDENCIES = ['yamllint>1,<2']


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
        '--script',
        choices=['check_config'])

    args = parser.parse_args()

    config_dir = os.path.join(os.getcwd(), args.config)
    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        print('Config directory does not exist:', config_dir)
        os.makedirs(config_dir)

    # Install DEPENDENCIES
    deps_dir = os.path.join(config_dir, 'deps')
    sys.path.insert(0, deps_dir)
    for req in DEPENDENCIES:
        if not pkg_util.install_package(req, target=deps_dir):
            print('Could not install dependency:', req)
            return 1

    yaml_files = ['-c', os.path.splitext(__file__)[0] + '.yaml']
    yaml_files.extend(glob.glob(os.path.join(config_dir, '*.yaml')))
    # Python 3.5 gets a recursive, but not in 3.4
    yaml_files.extend(glob.glob(os.path.join(config_dir, '*/*.yaml')))

    # Undo patching yaml to output OrderedDicts...
    import yaml
    from yaml import constructor
    yaml.SafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        constructor.SafeConstructor.construct_yaml_map)

    # Finally run yamllint
    import yamllint.cli
    yamllint.cli.run(yaml_files)

    return 0
