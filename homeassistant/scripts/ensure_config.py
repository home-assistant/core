"""Script to ensure a configuration file exists."""
import argparse
import os

from homeassistant.core import HomeAssistant
import homeassistant.config as config_util


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
        choices=['ensure_config'])

    args = parser.parse_args()

    config_dir = os.path.join(os.getcwd(), args.config)

    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        print('Creating directory', config_dir)
        os.makedirs(config_dir)

    hass = HomeAssistant()
    config_path = hass.loop.run_until_complete(async_run(hass, config_dir))
    print('Configuration file:', config_path)
    return 0


async def async_run(hass, config_dir):
    """Make sure config exists."""
    path = await config_util.async_ensure_config_exists(hass, config_dir)
    await hass.async_stop(force=True)
    return path
