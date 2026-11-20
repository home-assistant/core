"""Services tests for the Netgear LTE integration."""

from unittest.mock import patch

import pytest

from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.components.netgear_lte.services import NetgearLTEServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import HOST


async def test_set_option(hass: HomeAssistant, setup_integration: None) -> None:
    """Test service call set option."""
    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.set_failover_mode"
    ) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "set_option",
            {
                NetgearLTEServiceArgument.HOST: HOST,
                "failover": "auto",
                "autoconnect": "home",
            },
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 1

    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.connect_lte"
    ) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "connect_lte",
            {NetgearLTEServiceArgument.HOST: HOST},
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 1

    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.disconnect_lte"
    ) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "disconnect_lte",
            {NetgearLTEServiceArgument.HOST: HOST},
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 1

    with patch(
        "homeassistant.components.netgear_lte.eternalegypt.Modem.delete_sms"
    ) as mock_client:
        await hass.services.async_call(
            DOMAIN,
            "delete_sms",
            {NetgearLTEServiceArgument.HOST: HOST, "sms_id": 1},
            blocking=True,
        )
    assert len(mock_client.mock_calls) == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "delete_sms",
            {NetgearLTEServiceArgument.HOST: "no-match", "sms_id": 1},
            blocking=True,
        )
