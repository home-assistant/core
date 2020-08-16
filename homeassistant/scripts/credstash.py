"""Script to get, put and delete secrets stored in credstash."""
import argparse
import getpass

from homeassistant.util.yaml import _SECRET_NAMESPACE

# mypy: allow-untyped-defs

REQUIREMENTS = ["credstash==1.15.0"]


def run(args):
    """Handle credstash script."""
    parser = argparse.ArgumentParser(
        description=(
            "Modify Home Assistant secrets in credstash."
            "Use the secrets in configuration files with: "
            "!secret <name>"
        )
    )
    parser.add_argument("--script", choices=["credstash"])
    parser.add_argument(
        "action",
        choices=["get", "put", "del", "list"],
        help="Get, put or delete a secret, or list all available secrets",
    )
    parser.add_argument("name", help="Name of the secret", nargs="?", default=None)
    parser.add_argument(
        "value", help="The value to save when putting a secret", nargs="?", default=None
    )

    # pylint: disable=import-error, no-member, import-outside-toplevel
    import credstash

    args = parser.parse_args(args)
    table = _SECRET_NAMESPACE

    try:
        credstash.listSecrets(table=table)
    except Exception:  # pylint: disable=broad-except
        credstash.createDdbTable(table=table)

    if args.action == "list":
        secrets = [i["name"] for i in credstash.listSecrets(table=table)]
        deduped_secrets = sorted(set(secrets))

        print("Saved secrets:")
        for secret in deduped_secrets:
            print(secret)
        return 0

    if args.name is None:
        parser.print_help()
        return 1

    if args.action == "put":
        if args.value:
            the_secret = args.value
        else:
            the_secret = getpass.getpass(f"Please enter the secret for {args.name}: ")
        current_version = credstash.getHighestVersion(args.name, table=table)
        credstash.putSecret(
            args.name, the_secret, version=int(current_version) + 1, table=table
        )
        print(f"Secret {args.name} put successfully")
    elif args.action == "get":
        the_secret = credstash.getSecret(args.name, table=table)
        if the_secret is None:
            print(f"Secret {args.name} not found")
        else:
            print(f"Secret {args.name}={the_secret}")
    elif args.action == "del":
        credstash.deleteSecrets(args.name, table=table)
        print(f"Deleted secret {args.name}")
