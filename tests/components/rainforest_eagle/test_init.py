"""Tests for the Rainforest Eagle integration."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_200,
)
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT
from homeassistant.setup import async_setup_component


async def test_import(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.rainforest_eagle.data.async_get_type",
        return_value=(TYPE_EAGLE_200, "mock-hw"),
    ), patch(
        "homeassistant.components.rainforest_eagle.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": {
                    "platform": DOMAIN,
                    "ip_address": "192.168.1.55",
                    CONF_CLOUD_ID: "abcdef",
                    CONF_INSTALL_CODE: "123456",
                }
            },
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    assert entry.title == "abcdef"
    assert entry.data == {
        CONF_TYPE: TYPE_EAGLE_200,
        CONF_HOST: "192.168.1.55",
        CONF_CLOUD_ID: "abcdef",
        CONF_INSTALL_CODE: "123456",
        CONF_HARDWARE_ADDRESS: "mock-hw",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Second time we should get already_configured
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={CONF_CLOUD_ID: "abcdef", CONF_INSTALL_CODE: "123456"},
        context={"source": config_entries.SOURCE_IMPORT},
    )

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "already_configured"
