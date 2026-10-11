"""Tests for the Philips TV menu helpers."""

from unittest.mock import AsyncMock

from haphilipsjs import PhilipsTV
import pytest

from homeassistant.components.philips_js.helpers import (
    SettingsNotAvailable,
    get_node_paths,
    get_node_strings,
    get_path_names,
)

LEAF = {"node_id": 3, "type": "SLIDER_NODE", "context": "leaf", "data": {}}
ROOT = {
    "node_id": 1,
    "type": "PARENT_NODE",
    "string_id": "string.root",
    "data": {
        "nodes": [
            {
                "node_id": 2,
                "type": "PARENT_NODE",
                "context": "child",
                "data": {"nodes": [LEAF]},
            }
        ]
    },
}


def test_node_paths_not_supported(mock_tv: PhilipsTV) -> None:
    """Test no paths are returned if the TV has no menu support."""
    mock_tv.json_feature_supported.return_value = False

    assert list(get_node_paths(mock_tv)) == []


@pytest.mark.parametrize(
    ("on", "settings"),
    [(False, {"node": ROOT}), (True, None), (True, {})],
    ids=["off", "no-settings", "no-root-node"],
)
def test_node_paths_not_available(
    mock_tv: PhilipsTV, on: bool, settings: dict | None
) -> None:
    """Test the menu is not available."""
    mock_tv.json_feature_supported.return_value = True
    mock_tv.on = on
    mock_tv.settings = settings

    with pytest.raises(SettingsNotAvailable):
        list(get_node_paths(mock_tv))


async def test_node_paths_and_names(mock_tv: PhilipsTV) -> None:
    """Test the paths of the nodes and the names built from them."""
    mock_tv.json_feature_supported.return_value = True
    mock_tv.settings = {"node": ROOT}
    mock_tv.getStringsCached = AsyncMock(return_value={})

    paths = list(get_node_paths(mock_tv))
    names = await get_path_names(mock_tv, paths)

    assert [path[0]["node_id"] for path in paths] == [1, 2, 3]
    assert names == ["", "child", "child / leaf"]


def test_node_strings() -> None:
    """Test the translatable strings of a node."""
    node = {
        "node_id": 1,
        "string_id": "name",
        "data": {
            "enums": [{"enum_id": 0, "string_id": "enum"}],
            "sliders": [{"slider_id": "slider"}],
            "nodes": [{"node_id": 2, "string_id": "child"}, {"node_id": 3}],
        },
    }

    assert list(get_node_strings(node)) == ["name", "enum", "slider", "child"]
