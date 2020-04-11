"""Script to get, set and delete secrets stored in the keyring."""
import argparse
import getpass
import os

from homeassistant.util.yaml import _SECRET_NAMESPACE

# mypy: allow-untyped-defs
REQUIREMENTS = ["keyring==20.0.0", "keyrings.alt==3.4.0"]


def run(args):
    """Handle keyring script."""
    parser = argparse.ArgumentParser(
        description=(
            "Modify Home Assistant secrets in the default keyring. "
            "Use the secrets in configuration files with: "
            "!secret <name>"
        )
    )
    parser.add_argument("--script", choices=["keyring"])
    parser.add_argument(
        "action",
        choices=["get", "set", "del", "info"],
        help="Get, set or delete a secret",
    )
    parser.add_argument("name", help="Name of the secret", nargs="?", default=None)

    import keyring  # pylint: disable=import-outside-toplevel

    # pylint: disable=import-outside-toplevel
    from keyring.util import platform_ as platform

    args = parser.parse_args(args)

    if args.action == "info":
        keyr = keyring.get_keyring()
        print("Keyring version {}\n".format(REQUIREMENTS[0].split("==")[1]))
        print(f"Active keyring  : {keyr.__module__}")
        config_name = os.path.join(platform.config_root(), "keyringrc.cfg")
        print(f"Config location : {config_name}")
        print(f"Data location   : {platform.data_root()}\n")
    elif args.name is None:
        parser.print_help()
        return 1

    if args.action == "set":
        entered_secret = getpass.getpass(f"Please enter the secret for {args.name}: ")
        keyring.set_password(_SECRET_NAMESPACE, args.name, entered_secret)
        print(f"Secret {args.name} set successfully")
    elif args.action == "get":
        the_secret = keyring.get_password(_SECRET_NAMESPACE, args.name)
        if the_secret is None:
            print(f"Secret {args.name} not found")
        else:
            print(f"Secret {args.name}={the_secret}")
    elif args.action == "del":
        try:
            keyring.delete_password(_SECRET_NAMESPACE, args.name)
            print(f"Deleted secret {args.name}")
        except keyring.errors.PasswordDeleteError:
            print(f"Secret {args.name} not found")
