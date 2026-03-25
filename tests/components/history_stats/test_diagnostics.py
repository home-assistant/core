"""Tests for derivative diagnostics."""

import pytest

from homeassistant.components.history_stats.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("recorder_mock")
async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, loaded_entry
) -> None:
    """Test diagnostics for config entry."""

    result = await get_diagnostics_for_config_entry(hass, hass_client, loaded_entry)

    assert isinstance(result, dict)
    assert result["config_entry"]["domain"] == DOMAIN
    assert result["config_entry"]["options"][CONF_NAME] == DEFAULT_NAME
    assert (
        result["config_entry"]["options"][CONF_ENTITY_ID]
        == "binary_sensor.test_monitored"
    )
    assert result["entity"][0]["entity_id"] == "sensor.unnamed_statistics"
