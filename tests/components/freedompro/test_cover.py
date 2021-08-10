"""Tests for the Freedompro cover."""
from datetime import timedelta
from unittest.mock import ANY, patch

import pytest

from homeassistant.components.cover import ATTR_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.components.freedompro.const import DEVICES_STATE


@pytest.mark.parametrize(
    "entity_id, uid, name, model",
    [
        (
            "cover.blind",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS",
            "blind",
            "windowCovering",
        )
    ],
)
async def test_cover_get_state(
    hass, init_integration, entity_id: str, uid: str, name: str, model: str
):
    """Test states of the cover."""
    init_integration
    registry = er.async_get(hass)
    registry_device = dr.async_get(hass)

    device = registry_device.async_get_device({("freedompro", uid)})
    assert device is not None
    assert device.identifiers == {("freedompro", uid)}
    assert device.manufacturer == "Freedompro"
    assert device.name == name
    assert device.model == model

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_CLOSED
    assert state.attributes.get("friendly_name") == name

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    get_states_response = list(DEVICES_STATE)
    for state_response in get_states_response:
        if state_response["uid"] == uid:
            state_response["state"]["position"] = 100
    with patch(
        "homeassistant.components.freedompro.get_states",
        return_value=get_states_response,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes.get("friendly_name") == name

        entry = registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == uid

        assert state.state == STATE_OPEN


@pytest.mark.parametrize(
    "entity_id, uid, name, model",
    [
        (
            "cover.blind",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS",
            "blind",
            "windowCovering",
        )
    ],
)
async def test_cover_set_position(
    hass, init_integration, entity_id: str, uid: str, name: str, model: str
):
    """Test set position of the cover."""
    init_integration
    registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes.get("friendly_name") == name

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    with patch("homeassistant.components.freedompro.cover.put_state") as mock_put_state:
        assert await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: [entity_id], ATTR_POSITION: 33},
            blocking=True,
        )
    mock_put_state.assert_called_once_with(ANY, ANY, ANY, '{"position": 33}')

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OPEN


@pytest.mark.parametrize(
    "entity_id, uid, name, model",
    [
        (
            "cover.blind",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS",
            "blind",
            "windowCovering",
        )
    ],
)
async def test_cover_close(
    hass, init_integration, entity_id: str, uid: str, name: str, model: str
):
    """Test close cover."""
    init_integration
    registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes.get("friendly_name") == name

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    with patch("homeassistant.components.freedompro.cover.put_state") as mock_put_state:
        assert await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_put_state.assert_called_once_with(ANY, ANY, ANY, '{"position": 0}')

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OPEN


@pytest.mark.parametrize(
    "entity_id, uid, name, model",
    [
        (
            "cover.blind",
            "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*3XSSVIJWK-65HILWTC4WINQK46SP4OEZRCNO25VGWAS",
            "blind",
            "windowCovering",
        )
    ],
)
async def test_cover_open(
    hass, init_integration, entity_id: str, uid: str, name: str, model: str
):
    """Test open cover."""
    init_integration
    registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OPEN
    assert state.attributes.get("friendly_name") == name

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    with patch("homeassistant.components.freedompro.cover.put_state") as mock_put_state:
        assert await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_put_state.assert_called_once_with(ANY, ANY, ANY, '{"position": 100}')

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OPEN
