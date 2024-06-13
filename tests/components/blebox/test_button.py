"""Blebox button entities tests."""

import logging
from unittest.mock import PropertyMock

import blebox_uniapi
import pytest

from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant

from .conftest import async_setup_entity, mock_feature

query_icon_matching = [
    ("up", "mdi:arrow-up-circle"),
    ("down", "mdi:arrow-down-circle"),
    ("fav", "mdi:heart-circle"),
    ("open", "mdi:arrow-up-circle"),
    ("close", "mdi:arrow-down-circle"),
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

    return (feature, "button.tvliftbox_open_or_stop")


async def test_tvliftbox_init(
    tvliftbox, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test tvLiftBox initialisation."""
    caplog.set_level(logging.ERROR)

    _, entity_id = tvliftbox
    entry = await async_setup_entity(hass, entity_id)
    state = hass.states.get(entity_id)

    assert entry.unique_id == "BleBox-tvLiftBox-4a3fdaad90aa-open_or_stop"

    assert state.name == "tvLiftBox-open_or_stop"


@pytest.mark.parametrize("input", query_icon_matching)
async def test_get_icon(
    input, tvliftbox, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if proper icon is returned."""
    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = tvliftbox
    feature_mock.query_string = input[0]
    _ = await async_setup_entity(hass, entity_id)
    state = hass.states.get(entity_id)

    assert state.attributes[ATTR_ICON] == input[1]
