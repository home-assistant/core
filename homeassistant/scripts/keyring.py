"""Script to get, set and delete secrets stored in the keyring."""
import os
import argparse
import getpass

from homeassistant.util.yaml import _SECRET_NAMESPACE

REQUIREMENTS = ['keyring>=9.3,<10.0']


def run(args):
    """Handle keyring script."""
    parser = argparse.ArgumentParser(
        description=("Modify Home-Assistant secrets in the default keyring. "
                     "Use the secrets in configuration files with: "
                     "!secret <name>"))
    parser.add_argument(
        '--script', choices=['keyring'])
    parser.add_argument(
        'action', choices=['get', 'set', 'del', 'info'],
        help="Get, set or delete a secret")
    parser.add_argument(
        'name', help="Name of the secret", nargs='?', default=None)

    import keyring
    from keyring.util import platform_ as platform

    args = parser.parse_args(args)

    if args.action == 'info':
        keyr = keyring.get_keyring()
        print('Keyring version {}\n'.format(keyring.__version__))
        print('Active keyring  : {}'.format(keyr.__module__))
        config_name = os.path.join(platform.config_root(), 'keyringrc.cfg')
        print('Config location : {}'.format(config_name))
        print('Data location   : {}\n'.format(platform.data_root()))
    elif args.name is None:
        parser.print_help()
        return 1

    if args.action == 'set':
        the_secret = getpass.getpass('Please enter the secret for {}: '
                                     .format(args.name))
        keyring.set_password(_SECRET_NAMESPACE, args.name, the_secret)
        print('Secret {} set successfully'.format(args.name))
    elif args.action == 'get':
        the_secret = keyring.get_password(_SECRET_NAMESPACE, args.name)
        if the_secret is None:
            print('Secret {} not found'.format(args.name))
        else:
            print('Secret {}={}'.format(args.name, the_secret))
    elif args.action == 'del':
        try:
            keyring.delete_password(_SECRET_NAMESPACE, args.name)
            print('Deleted secret {}'.format(args.name))
        except keyring.errors.PasswordDeleteError:
            print('Secret {} not found'.format(args.name))
