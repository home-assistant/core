"""Blebox button entities tests."""

import logging
from unittest.mock import PropertyMock

import blebox_uniapi
import pytest

from homeassistant.core import HomeAssistant

from .conftest import async_setup_entity, mock_feature

query_translation_key_matching = [
    ("up", "up", "button.my_tvliftbox_up", "My tvLiftBox Up"),
    ("down", "down", "button.my_tvliftbox_down", "My tvLiftBox Down"),
    ("fav", "fav", "button.my_tvliftbox_favorite", "My tvLiftBox Favorite"),
    ("open", "open", "button.my_tvliftbox_open", "My tvLiftBox Open"),
    ("close", "close", "button.my_tvliftbox_close", "My tvLiftBox Close"),
    ("unknown_action", None, "button.my_tvliftbox", "My tvLiftBox"),
]


@pytest.fixture(name="tvliftbox")
def tv_lift_box_fixture(caplog: pytest.LogCaptureFixture):
    """Return simple button entity mock."""
    caplog.set_level(logging.ERROR)

    feature = mock_feature(
        "buttons",
        blebox_uniapi.button.Button,
        unique_id="BleBox-tvLiftBox-4a3fdaad90aa-open_or_stop",
        full_name="tvLiftBox-open_or_stop",
        control_type=blebox_uniapi.button.ControlType.OPEN,
    )

    product = feature.product
    type(product).name = PropertyMock(return_value="My tvLiftBox")
    type(product).model = PropertyMock(return_value="tvLiftBox")
    type(product)._query_string = PropertyMock(return_value="open_or_stop")

    return (feature, "button.my_tvliftbox")


async def test_tvliftbox_init(
    tvliftbox, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test tvLiftBox initialisation."""
    caplog.set_level(logging.ERROR)

    _, entity_id = tvliftbox
    entry = await async_setup_entity(hass, entity_id)
    state = hass.states.get(entity_id)

    assert entry.unique_id == "BleBox-tvLiftBox-4a3fdaad90aa-open_or_stop"

    assert state.name == "My tvLiftBox"


@pytest.mark.parametrize(
    ("query_string", "expected_translation_key", "expected_entity_id", "expected_name"),
    query_translation_key_matching,
    ids=[q[0] for q in query_translation_key_matching],
)
async def test_button_translation_key(
    query_string: str,
    expected_translation_key: str | None,
    expected_entity_id: str,
    expected_name: str,
    tvliftbox: tuple[blebox_uniapi.button.Button, str],
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the correct translation_key is assigned based on query_string."""
    caplog.set_level(logging.ERROR)

    feature_mock, _ = tvliftbox
    feature_mock.query_string = query_string
    entity = await async_setup_entity(hass, expected_entity_id)
    assert entity is not None
    assert entity.translation_key == expected_translation_key

    state = hass.states.get(expected_entity_id)
    assert state is not None
    assert state.name == expected_name
