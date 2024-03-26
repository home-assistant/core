"""Test Hue services."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components import hue
from homeassistant.components.hue import bridge
from homeassistant.components.hue.const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_UNREACHABLE,
)
from homeassistant.core import HomeAssistant

from .conftest import setup_bridge, setup_component

GROUP_RESPONSE = {
    "group_1": {
        "name": "Group 1",
        "lights": ["1", "2"],
        "type": "LightGroup",
        "action": {
            "on": True,
            "bri": 254,
            "hue": 10000,
            "sat": 254,
            "effect": "none",
            "xy": [0.5, 0.5],
            "ct": 250,
            "alert": "select",
            "colormode": "ct",
        },
        "state": {"any_on": True, "all_on": False},
    }
}
SCENE_RESPONSE = {
    "scene_1": {
        "name": "Cozy dinner",
        "lights": ["1", "2"],
        "owner": "ffffffffe0341b1b376a2389376a2389",
        "recycle": True,
        "locked": False,
        "appdata": {"version": 1, "data": "myAppData"},
        "picture": "",
        "lastupdated": "2015-12-03T10:09:22",
        "version": 2,
    }
}


async def test_hue_activate_scene(hass: HomeAssistant, mock_api_v1) -> None:
    """Test successful hue_activate_scene."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=hue.DOMAIN,
        title="Mock Title",
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        source="test",
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )

    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    with (
        patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1):
        assert (
            await hue.services.hue_activate_scene_v1(
                hue_bridge, "Group 1", "Cozy dinner"
            )
            is True
        )

    assert len(mock_api_v1.mock_requests) == 3
    assert mock_api_v1.mock_requests[2]["json"]["scene"] == "scene_1"
    assert "transitiontime" not in mock_api_v1.mock_requests[2]["json"]
    assert mock_api_v1.mock_requests[2]["path"] == "groups/group_1/action"


async def test_hue_activate_scene_transition(hass: HomeAssistant, mock_api_v1) -> None:
    """Test successful hue_activate_scene with transition."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=hue.DOMAIN,
        title="Mock Title",
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        source="test",
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )

    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    with (
        patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1

    with patch("aiohue.HueBridgeV1", return_value=mock_api_v1):
        assert (
            await hue.services.hue_activate_scene_v1(
                hue_bridge, "Group 1", "Cozy dinner", 30
            )
            is True
        )

    assert len(mock_api_v1.mock_requests) == 3
    assert mock_api_v1.mock_requests[2]["json"]["scene"] == "scene_1"
    assert mock_api_v1.mock_requests[2]["json"]["transitiontime"] == 30
    assert mock_api_v1.mock_requests[2]["path"] == "groups/group_1/action"


async def test_hue_activate_scene_group_not_found(
    hass: HomeAssistant, mock_api_v1
) -> None:
    """Test failed hue_activate_scene due to missing group."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=hue.DOMAIN,
        title="Mock Title",
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        source="test",
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )

    mock_api_v1.mock_group_responses.append({})
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    with (
        patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1

    with patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1):
        assert (
            await hue.services.hue_activate_scene_v1(
                hue_bridge, "Group 1", "Cozy dinner"
            )
            is False
        )


async def test_hue_activate_scene_scene_not_found(
    hass: HomeAssistant, mock_api_v1
) -> None:
    """Test failed hue_activate_scene due to missing scene."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=hue.DOMAIN,
        title="Mock Title",
        data={"host": "1.2.3.4", "api_key": "mock-api-key", "api_version": 1},
        source="test",
        options={CONF_ALLOW_HUE_GROUPS: True, CONF_ALLOW_UNREACHABLE: False},
    )

    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append({})

    with (
        patch.object(bridge, "HueBridgeV1", return_value=mock_api_v1),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        hue_bridge = bridge.HueBridge(hass, config_entry)
        assert await hue_bridge.async_initialize_bridge() is True

    assert hue_bridge.api is mock_api_v1

    with patch("aiohue.HueBridgeV1", return_value=mock_api_v1):
        assert (
            await hue.services.hue_activate_scene_v1(
                hue_bridge, "Group 1", "Cozy dinner"
            )
            is False
        )


async def test_hue_multi_bridge_activate_scene_all_respond(
    hass: HomeAssistant,
    mock_bridge_v1,
    mock_bridge_v2,
    mock_config_entry_v1,
    mock_config_entry_v2,
) -> None:
    """Test that makes multiple bridges successfully activate a scene."""
    await setup_component(hass)

    mock_api_v1 = mock_bridge_v1.api
    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    await setup_bridge(hass, mock_bridge_v1, mock_config_entry_v1)
    await setup_bridge(hass, mock_bridge_v2, mock_config_entry_v2)

    with patch.object(
        hue.services, "hue_activate_scene_v2", return_value=True
    ) as mock_hue_activate_scene2:
        await hass.services.async_call(
            "hue",
            "hue_activate_scene",
            {"group_name": "Group 1", "scene_name": "Cozy dinner"},
            blocking=True,
        )

    assert len(mock_api_v1.mock_requests) == 3
    assert mock_api_v1.mock_requests[2]["json"]["scene"] == "scene_1"
    assert mock_api_v1.mock_requests[2]["path"] == "groups/group_1/action"

    mock_hue_activate_scene2.assert_called_once()


async def test_hue_multi_bridge_activate_scene_one_responds(
    hass: HomeAssistant,
    mock_bridge_v1,
    mock_bridge_v2,
    mock_config_entry_v1,
    mock_config_entry_v2,
) -> None:
    """Test that makes only one bridge successfully activate a scene."""
    await setup_component(hass)

    mock_api_v1 = mock_bridge_v1.api
    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    await setup_bridge(hass, mock_bridge_v1, mock_config_entry_v1)
    await setup_bridge(hass, mock_bridge_v2, mock_config_entry_v2)

    with patch.object(
        hue.services, "hue_activate_scene_v2", return_value=False
    ) as mock_hue_activate_scene2:
        await hass.services.async_call(
            "hue",
            "hue_activate_scene",
            {"group_name": "Group 1", "scene_name": "Cozy dinner"},
            blocking=True,
        )

    assert len(mock_api_v1.mock_requests) == 3
    assert mock_api_v1.mock_requests[2]["json"]["scene"] == "scene_1"
    assert mock_api_v1.mock_requests[2]["path"] == "groups/group_1/action"
    mock_hue_activate_scene2.assert_called_once()


async def test_hue_multi_bridge_activate_scene_zero_responds(
    hass: HomeAssistant,
    mock_bridge_v1,
    mock_bridge_v2,
    mock_config_entry_v1,
    mock_config_entry_v2,
) -> None:
    """Test that makes no bridge successfully activate a scene."""
    await setup_component(hass)
    mock_api_v1 = mock_bridge_v1.api
    mock_api_v1.mock_group_responses.append(GROUP_RESPONSE)
    mock_api_v1.mock_scene_responses.append(SCENE_RESPONSE)

    await setup_bridge(hass, mock_bridge_v1, mock_config_entry_v1)
    await setup_bridge(hass, mock_bridge_v2, mock_config_entry_v2)

    with patch.object(
        hue.services, "hue_activate_scene_v2", return_value=False
    ) as mock_hue_activate_scene2:
        await hass.services.async_call(
            "hue",
            "hue_activate_scene",
            {"group_name": "Non existing group", "scene_name": "Non existing Scene"},
            blocking=True,
        )

    # the V1 implementation should have retried (2 calls)
    assert len(mock_api_v1.mock_requests) == 2
    assert mock_hue_activate_scene2.call_count == 1
