"""Script to manage users for the Home Assistant auth provider."""
import argparse
import os

from homeassistant.config import get_default_config_dir
from homeassistant.auth_providers import homeassistant as hass_auth


def run(args):
    """Handle Home Assistant auth provider script."""
    parser = argparse.ArgumentParser(
        description=("Manage Home Assistant users"))
    parser.add_argument(
        '--script', choices=['auth'])
    parser.add_argument(
        '-c', '--config',
        default=get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")

    subparsers = parser.add_subparsers()
    parser_list = subparsers.add_parser('list')
    parser_list.set_defaults(func=list_users)

    parser_add = subparsers.add_parser('add')
    parser_add.add_argument('username', type=str)
    parser_add.add_argument('password', type=str)
    parser_add.set_defaults(func=add_user)

    parser_validate_login = subparsers.add_parser('validate')
    parser_validate_login.add_argument('username', type=str)
    parser_validate_login.add_argument('password', type=str)
    parser_validate_login.set_defaults(func=validate_login)

    parser_change_pw = subparsers.add_parser('change_password')
    parser_change_pw.add_argument('username', type=str)
    parser_change_pw.add_argument('new_password', type=str)
    parser_change_pw.set_defaults(func=change_password)

    args = parser.parse_args(args)
    path = os.path.join(os.getcwd(), args.config, hass_auth.PATH_DATA)
    args.func(hass_auth.load_data(path), args)


def list_users(data, args):
    """List the users."""
    count = 0
    for user in data.users:
        count += 1
        print(user['username'])

    print()
    print("Total users:", count)


def add_user(data, args):
    """Create a user."""
    data.add_user(args.username, args.password)
    data.save()
    print("User created")


def validate_login(data, args):
    """Validate a login."""
    try:
        data.validate_login(args.username, args.password)
        print("Auth valid")
    except hass_auth.InvalidAuth:
        print("Auth invalid")


def change_password(data, args):
    """Change password."""
    try:
        data.change_password(args.username, args.new_password)
        data.save()
        print("Password changed")
    except hass_auth.InvalidUser:
        print("User not found")
