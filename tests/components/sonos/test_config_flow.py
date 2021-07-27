"""Test the sonos config flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant import config_entries, core, setup
from homeassistant.components.sonos.const import DATA_SONOS_DISCOVERY_MANAGER, DOMAIN


@patch("homeassistant.components.sonos.config_flow.soco.discover", return_value=True)
async def test_user_form(discover_mock: MagicMock, hass: core.HomeAssistant):
    """Test we get the user initiated form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sonos"
    assert result2["data"] == {}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_form(hass: core.HomeAssistant):
    """Test we pass sonos devices to the discovery manager."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = MagicMock()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "host": "192.168.4.2",
            "hostname": "Sonos-aaa",
            "properties": {"bootseq": "1234"},
        },
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sonos"
    assert result2["data"] == {}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_manager.mock_calls) == 2


async def test_zeroconf_form_not_sonos(hass: core.HomeAssistant):
    """Test we abort on non-sonos devices."""
    mock_manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = MagicMock()
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "host": "192.168.4.2",
            "hostname": "not-aaa",
            "properties": {"bootseq": "1234"},
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_sonos_device"
    assert len(mock_manager.mock_calls) == 0
