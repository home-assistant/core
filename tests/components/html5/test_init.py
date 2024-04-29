"""Test the HTML5 setup."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

NOTIFY_CONF = {
    "notify": [
        {
            "platform": "html5",
            "name": "html5",
            "vapid_pub_key": "BIUtPN7Rq_8U7RBEqClZrfZ5dR9zPCfvxYPtLpWtRVZTJEc7lzv2dhzDU6Aw1m29Ao0-UA1Uq6XO9Df8KALBKqA",
            "vapid_prv_key": "h6acSRds8_KR8hT9djD8WucTL06Gfe29XXyZ1KcUjN8",
            "vapid_email": "test@example.com",
        }
    ]
}


async def test_setup_entry(
    hass: HomeAssistant,
) -> None:
    """Test setup of a good config entry."""
    with patch(
        "homeassistant.components.html5.async_create_html5_issue"
    ) as mock_async_create_html5_issue:
        config_entry = MockConfigEntry(domain="html5", data={})
        config_entry.add_to_hass(hass)
        assert await async_setup_component(hass, "html5", {})
        assert mock_async_create_html5_issue.call_count == 0


async def test_setup_entry_issue(
    hass: HomeAssistant,
) -> None:
    """Test setup of an imported config entry with deprecated YAML."""
    with patch(
        "homeassistant.components.html5.async_create_html5_issue"
    ) as mock_async_create_html5_issue:
        config_entry = MockConfigEntry(domain="html5", data={})
        config_entry.add_to_hass(hass)
        assert await async_setup_component(hass, "html5", NOTIFY_CONF)
        assert mock_async_create_html5_issue.call_count == 1
