"""Services tests for the Netgear LTE integration."""

from unittest.mock import patch

from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .conftest import HOST


async def test_set_option(hass: HomeAssistant, setup_integration: None) -> None:
    """Test service call set option."""
    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.set_failover_mode"
    ) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "set_option",
            {CONF_HOST: HOST, "failover": "auto", "autoconnect": "home"},
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 1

    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.connect_lte"
    ) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "connect_lte",
            {CONF_HOST: HOST},
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 1

    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.disconnect_lte"
    ) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "disconnect_lte",
            {CONF_HOST: HOST},
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 1

    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.delete_sms"
    ) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "delete_sms",
            {CONF_HOST: HOST, "sms_id": 1},
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 1
