"""Test the Ecowitt Weather Station config flow."""

from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.ecowitt.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we can create a config entry."""
    await async_setup_component(hass, "http", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.ecowitt.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Ecowitt"
    assert result2["data"] == {
        "webhook_id": result2["description_placeholders"]["path"].split("/")[-1],
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("core_config", "use_ssl", "expected_server", "expected_port"),
    [
        pytest.param(
            {"internal_url": "https://ha.example.com"},
            False,
            "192.168.1.10",
            "8123",
            id="https_internal_url_behind_proxy",
        ),
        pytest.param(
            {"external_url": "https://ha.example.com"},
            False,
            "192.168.1.10",
            "8123",
            id="https_external_url_only",
        ),
        pytest.param(
            {"internal_url": "http://ha.local:8123"},
            False,
            "ha.local",
            "8123",
            id="http_internal_url",
        ),
        pytest.param(
            {"external_url": "https://ha.example.com"},
            True,
            "ha.example.com",
            "443",
            id="home_assistant_serves_https",
        ),
    ],
)
async def test_create_entry_station_target(
    hass: HomeAssistant,
    core_config: dict[str, str],
    use_ssl: bool,
    expected_server: str,
    expected_port: str,
) -> None:
    """Test the station is pointed at a plain HTTP local address when possible."""
    await async_setup_component(hass, "http", {})
    await async_process_ha_core_config(hass, core_config)
    hass.config.api = Mock(local_ip="192.168.1.10", port=8123, use_ssl=use_ssl)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.ecowitt.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["description_placeholders"]["server"] == expected_server
    assert result["description_placeholders"]["port"] == expected_port
