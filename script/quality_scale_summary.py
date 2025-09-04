"""Generate a summary of integration quality scales.

Run with python3 -m script.quality_scale_summary
Data collected at https://docs.google.com/spreadsheets/d/1xEiwovRJyPohAv8S4ad2LAB-0A38s1HWmzHng8v-4NI
"""

import csv
from pathlib import Path
import sys

from homeassistant.const import __version__ as current_version
from homeassistant.util.json import load_json

COMPONENTS_DIR = Path("homeassistant/components")


def generate_quality_scale_summary() -> list[str, int]:
    """Generate a summary of integration quality scales."""
    quality_scales = {
        "virtual": 0,
        "unknown": 0,
        "legacy": 0,
        "internal": 0,
        "bronze": 0,
        "silver": 0,
        "gold": 0,
        "platinum": 0,
    }

    for manifest_path in COMPONENTS_DIR.glob("*/manifest.json"):
        manifest = load_json(manifest_path)

        if manifest.get("integration_type") == "virtual":
            quality_scales["virtual"] += 1
        elif quality_scale := manifest.get("quality_scale"):
            quality_scales[quality_scale] += 1
        else:
            quality_scales["unknown"] += 1

    return quality_scales


def output_csv(quality_scales: dict[str, int], print_header: bool) -> None:
    """Output the quality scale summary as CSV."""
    writer = csv.writer(sys.stdout)
    if print_header:
        writer.writerow(
            [
                "Version",
                "Total",
                "Virtual",
                "Unknown",
                "Legacy",
                "Internal",
                "Bronze",
                "Silver",
                "Gold",
                "Platinum",
            ]
        )

    # Calculate total
    total = sum(quality_scales.values())

    # Write the summary
    writer.writerow(
        [
            current_version,
            total,
            quality_scales["virtual"],
            quality_scales["unknown"],
            quality_scales["legacy"],
            quality_scales["internal"],
            quality_scales["bronze"],
            quality_scales["silver"],
            quality_scales["gold"],
            quality_scales["platinum"],
        ]
    )


def main() -> None:
    """Run the script."""
    quality_scales = generate_quality_scale_summary()
    output_csv(quality_scales, "--header" in sys.argv)


if __name__ == "__main__":
    main()
