"""Test Matter node fixtures."""

from collections import defaultdict
import json
from pathlib import Path


def test_node_fixtures_have_unique_node_ids() -> None:
    """Ensure all Matter node fixtures have unique node IDs."""
    fixtures_dir = Path(__file__).parent / "fixtures" / "nodes"

    node_ids: dict[int, list[str]] = defaultdict(list)

    for fixture in sorted(fixtures_dir.glob("*.json")):
        data = json.loads(fixture.read_text(encoding="utf-8"))
        node_ids[data["node_id"]].append(fixture.name)

    duplicates = {
        node_id: files for node_id, files in node_ids.items() if len(files) > 1
    }

    assert not duplicates, "Duplicate Matter node IDs found:\n" + "\n".join(
        f"  node_id {node_id}: {', '.join(files)}"
        for node_id, files in sorted(duplicates.items())
    )
