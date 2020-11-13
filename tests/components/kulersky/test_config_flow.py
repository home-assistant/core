"""Test the Kuler Sky config flow."""
import pykulersky

from homeassistant import config_entries, setup
from homeassistant.components.kulersky.config_flow import DOMAIN

from tests.async_mock import patch


async def test_flow_success(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.kulersky.config_flow.pykulersky.discover_bluetooth_devices",
        return_value=[
            {
                "address": "AA:BB:CC:11:22:33",
                "name": "Bedroom",
            }
        ],
    ), patch(
        "homeassistant.components.kulersky.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.kulersky.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Kuler Sky"
    assert result2["data"] == {}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_no_devices_found(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.kulersky.config_flow.pykulersky.discover_bluetooth_devices",
        return_value=[],
    ), patch(
        "homeassistant.components.kulersky.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.kulersky.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_flow_exceptions_caught(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.kulersky.config_flow.pykulersky.discover_bluetooth_devices",
        side_effect=pykulersky.PykulerskyException("TEST"),
    ), patch(
        "homeassistant.components.kulersky.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.kulersky.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "no_devices_found"
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0
