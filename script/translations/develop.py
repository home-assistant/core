"""Compile the current translation strings files for testing."""
import argparse
import json
from pathlib import Path
from shutil import rmtree
import sys

from . import download, upload
from .const import INTEGRATIONS_DIR
from .util import get_base_arg_parser


def valid_integration(integration):
    """Test if it's a valid integration."""
    if not (INTEGRATIONS_DIR / integration).is_dir():
        raise argparse.ArgumentTypeError(
            f"The integration {integration} does not exist."
        )

    return integration


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = get_base_arg_parser()
    parser.add_argument(
        "--integration", type=valid_integration, help="Integration to process."
    )
    return parser.parse_args()


def run():
    """Run the script."""
    args = get_arguments()
    if args.integration:
        integration = args.integration
    else:
        integration = None
        while (
            integration is None
            or not Path(f"homeassistant/components/{integration}").exists()
        ):
            if integration is not None:
                print(f"Integration {integration} doesn't exist!")
                print()
            integration = input("Integration to process: ")

    translations = upload.generate_upload_data()

    if integration not in translations["component"]:
        print("Integration has no strings.json")
        sys.exit(1)

    if download.DOWNLOAD_DIR.is_dir():
        rmtree(str(download.DOWNLOAD_DIR))

    download.DOWNLOAD_DIR.mkdir(parents=True)

    (download.DOWNLOAD_DIR / "en.json").write_text(
        json.dumps({"component": {integration: translations["component"][integration]}})
    )

    download.write_integration_translations()
