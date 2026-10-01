"""Test the Home Assistant package init."""

import subprocess
import sys

IMPORT_TIMEOUT = 60


def test_to_field_list_resolves_at_import() -> None:
    """Config flow forms render from the event loop, so the import cannot happen there.

    Probatio resolves to_field_list through a lazy import on first attribute
    access. Importing the name binds it instead, while the helper itself is
    imported. A clean interpreter is the only way to see this: anything the test
    suite imported first would hide it.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import homeassistant.helpers.data_entry_flow, probatio;"
            " print('to_field_list' in vars(probatio))",
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=IMPORT_TIMEOUT,
    )

    assert result.stdout.strip() == "True"
