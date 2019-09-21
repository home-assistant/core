"""Generate an integration."""
import json
from pathlib import Path

from .const import COMPONENT_DIR, TESTS_DIR
from .model import Info

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_INTEGRATION = TEMPLATE_DIR / "integration"
TEMPLATE_TESTS = TEMPLATE_DIR / "tests"


def generate(info: Info) -> None:
    """Generate an integration."""
    print(f"Generating the {info.domain} integration...")
    integration_dir = COMPONENT_DIR / info.domain
    test_dir = TESTS_DIR / info.domain

    replaces = {
        "NEW_DOMAIN": info.domain,
        "NEW_NAME": info.name,
        "NEW_CODEOWNER": info.codeowner,
        # Special case because we need to keep the list empty if there is none.
        '"MANIFEST_NEW_REQUIREMENT"': (
            json.dumps(info.requirement) if info.requirement else ""
        ),
    }

    for src_dir, target_dir in (
        (TEMPLATE_INTEGRATION, integration_dir),
        (TEMPLATE_TESTS, test_dir),
    ):
        # Guard making it for test purposes.
        if not target_dir.exists():
            target_dir.mkdir()

        for source_file in src_dir.glob("**/*"):
            content = source_file.read_text()

            for to_search, to_replace in replaces.items():
                content = content.replace(to_search, to_replace)

            target_file = target_dir / source_file.relative_to(src_dir)
            print(f"Writing {target_file}")
            target_file.write_text(content)

    print()
