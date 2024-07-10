"""Script to convert a device diagnostics file to a fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from homeassistant.util import slugify


def get_arguments() -> argparse.Namespace:
    """Get parsed passed in arguments."""
    parser = argparse.ArgumentParser(description="Z-Wave JS Fixture generator")
    parser.add_argument(
        "diagnostics_file", type=Path, help="Device diagnostics file to convert"
    )
    parser.add_argument(
        "--file",
        action="store_true",
        help=(
            "Dump fixture to file in fixtures folder. By default, the fixture will be "
            "printed to standard output."
        ),
    )

    return parser.parse_args()


def get_fixtures_dir_path(data: dict) -> Path:
    """Get path to fixtures directory."""
    device_config = data["deviceConfig"]
    filename = slugify(
        f"{device_config['manufacturer']}-{device_config['label']}_state"
    )
    path = Path(__file__).parents[1]
    index = path.parts.index("homeassistant")
    return Path(
        *path.parts[:index],
        "tests",
        *path.parts[index + 1 :],
        "fixtures",
        f"{filename}.json",
    )


def load_file(path: Path) -> Any:
    """Load file from path."""
    return json.loads(path.read_text("utf8"))


def extract_fixture_data(diagnostics_data: Any) -> dict:
    """Extract fixture data from file."""
    if (
        not isinstance(diagnostics_data, dict)
        or "data" not in diagnostics_data
        or "state" not in diagnostics_data["data"]
    ):
        raise ValueError("Invalid diagnostics file format")
    state: dict = diagnostics_data["data"]["state"]
    if not isinstance(state["values"], list):
        values_dict: dict[str, dict] = state.pop("values")
        state["values"] = list(values_dict.values())
    if not isinstance(state["endpoints"], list):
        endpoints_dict: dict[str, dict] = state.pop("endpoints")
        state["endpoints"] = list(endpoints_dict.values())

    return state


def create_fixture_file(path: Path, state_text: str) -> None:
    """Create a file for the state dump in the fixtures directory."""
    path.write_text(state_text, "utf8")


def main() -> None:
    """Run the main script."""
    args = get_arguments()
    diagnostics_path: Path = args.diagnostics_file
    diagnostics = load_file(diagnostics_path)
    fixture_data = extract_fixture_data(diagnostics)
    fixture_text = json.dumps(fixture_data, indent=2)
    if args.file:
        fixture_path = get_fixtures_dir_path(fixture_data)
        create_fixture_file(fixture_path, fixture_text)
        return
    print(fixture_text)  # noqa: T201


if __name__ == "__main__":
    main()
