"""Script to retrieve information about a Home Assistant instance."""

import argparse
import pprint

import homeassistant.remote as remote

def run(args):
    """The actual script body."""
    # pylint: disable=too-many-locals,invalid-name,too-many-statements
    parser = argparse.ArgumentParser(
        description="Command-line interface for a Home Assistant instance")
    parser.add_argument(
        '-i', '--info',
        action='store_true',
        default=False,
        help="show information about a Home Assistant instance")
    parser.add_argument(
        '-s', '--services',
        action='store_true',
        default=False,
        help="get all available services.")
    parser.add_argument(
        '-e', '--entities',
        action='store_true',
        default=False,
        help="get all entity states.")
    parser.add_argument(
        '-p', '--password',
        metavar='api_password',
        required=True,
        help="the API password for the Home Assistant instance")
    parser.add_argument(
        '-r', '--remote',
        metavar='ha_instance',
        default='127.0.0.1',
        help="the IP address of the Home Assistant instance")
    parser.add_argument(
        '--script',
        choices=['commandline'])

    args = parser.parse_args()

    api = remote.API(args.remote, args.password)
    if remote.validate_api(api) == 'invalid_password':
        print('Fatal Error: Password is not valid')
        return 1

    if args.info:
        pprint.pprint(remote.get_config(api))

    if args.services:
        services = remote.get_services(api)
        for service in services:
            pprint.pprint(service['services'], depth=4, width=78)

    if args.entities:
        entities = remote.get_states(api)
        for entity in entities:
            print('{} is {}'.format(entity.attributes['friendly_name'],
                                    entity.state))

    return 0
