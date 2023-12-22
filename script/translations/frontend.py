"""Write updated translations to the frontend."""
import argparse
import json

from .const import FRONTEND_DIR
from .download import DOWNLOAD_DIR, run_download_docker
from .util import get_base_arg_parser, load_json_from_path

FRONTEND_BACKEND_TRANSLATIONS = FRONTEND_DIR / "translations/backend"


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = get_base_arg_parser()
    parser.add_argument(
        "--skip-download", action="store_true", help="Skip downloading translations."
    )
    return parser.parse_args()


def run():
    """Update frontend translations with backend data.

    We use the downloaded Docker files because it gives us each language in 1 file.
    """
    args = get_arguments()

    if not args.skip_download:
        run_download_docker()

    for lang_file in DOWNLOAD_DIR.glob("*.json"):
        translations = load_json_from_path(lang_file)

        to_write_translations = {"component": {}}

        for domain, domain_translations in translations["component"].items():
            if "state" not in domain_translations:
                continue

            to_write_translations["component"][domain] = {
                "state": domain_translations["state"]
            }

        (FRONTEND_BACKEND_TRANSLATIONS / lang_file.name).write_text(
            json.dumps(to_write_translations, indent=2)
        )
