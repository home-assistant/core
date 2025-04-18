"""Test the Lovelace initialization."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture
def mock_onboarding_done() -> Generator[MagicMock]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=True,
    ) as mock_onboarding:
        yield mock_onboarding


async def test_create_dashboards_when_onboarded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    mock_onboarding_done,
) -> None:
    """Test we don't create dashboards when onboarded."""
    client = await hass_ws_client(hass)

    assert await async_setup_component(hass, "lovelace", {})

    # List dashboards
    await client.send_json_auto_id({"type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []


@pytest.mark.parametrize("integration_frame_path", ["custom_components/my_integration"])
@pytest.mark.usefixtures("mock_integration_frame")
async def test_hass_data_compatibility(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test compatibility for external access.

    See:
    https://github.com/hacs/integration/blob/4a820e8b1b066bc54a1c9c61102038af6c030603
    /custom_components/hacs/repositories/plugin.py#L173
    """
    expected_prefix = (
        "Detected that custom integration 'my_integration' accessed lovelace_data"
    )

    assert await async_setup_component(hass, "lovelace", {})

    assert (lovelace_data := hass.data.get("lovelace")) is not None

    # Direct access to resources is fine
    assert lovelace_data.resources is not None
    assert expected_prefix not in caplog.text

    # Dict compatibility logs warning
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()):
        assert lovelace_data["resources"] is not None
    assert f"{expected_prefix}['resources']" in caplog.text

    # Dict get compatibility logs warning
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()):
        assert lovelace_data.get("resources") is not None
    assert f"{expected_prefix}.get('resources')" in caplog.text
