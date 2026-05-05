"""Axis event platform tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    DOMAIN as EVENT_DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import ConfigEntryFactoryType, RtspEventMock


async def test_doorbell_event_entity_created_and_triggered(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    mock_rtsp_event: RtspEventMock,
) -> None:
    """Test doorbell event entity creation and trigger for matching model and port."""
    with patch("homeassistant.components.axis.PLATFORMS", [Platform.EVENT]):
        config_entry = await config_entry_factory()

    config_entry.runtime_data.config.model = "I8116-E"

    mock_rtsp_event(
        topic="tns1:Device/tnsaxis:IO/Port",
        data_type="state",
        data_value="0",
        operation="Initialized",
        source_name="port",
        source_idx="0",
    )
    await hass.async_block_till_done()

    event_entities = hass.states.async_entity_ids(EVENT_DOMAIN)
    assert len(event_entities) == 1

    state = hass.states.get(event_entities[0])
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPES] == ["ring"]

    mock_rtsp_event(
        topic="tns1:Device/tnsaxis:IO/Port",
        data_type="state",
        data_value="1",
        operation="Changed",
        source_name="port",
        source_idx="0",
    )
    await hass.async_block_till_done()

    state = hass.states.get(event_entities[0])
    assert state is not None
    assert state.attributes[ATTR_EVENT_TYPE] == "ring"


@pytest.mark.parametrize(
    ("model", "topic", "source_idx"),
    [
        ("A1234", "tns1:Device/tnsaxis:IO/Port", "0"),
        ("I8116-E", "tns1:Device/tnsaxis:IO/Port", "1"),
        ("I8116-E", "tns1:Device/tnsaxis:Sensor/PIR", "0"),
    ],
)
async def test_doorbell_event_entity_filtering(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    mock_rtsp_event: RtspEventMock,
    model: str,
    topic: str,
    source_idx: str,
) -> None:
    """Test doorbell event entity is filtered by model, topic and port."""
    with patch("homeassistant.components.axis.PLATFORMS", [Platform.EVENT]):
        config_entry = await config_entry_factory()

    config_entry.runtime_data.config.model = model

    mock_rtsp_event(
        topic=topic,
        data_type="state",
        data_value="1",
        operation="Initialized",
        source_name="port",
        source_idx=source_idx,
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(EVENT_DOMAIN)) == 0
