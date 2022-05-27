"""Test the Loqed config flow."""
import json
from unittest.mock import Mock, patch

import aiohttp
from loqedAPI import loqed

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.loqed.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import load_fixture


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    loqed_integration_config = load_fixture("loqed/integration_config.json")

    mock_lock = Mock(spec=loqed.Lock, id="Foo")

    with patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock",
        return_value=mock_lock,
    ), patch(
        "homeassistant.components.loqed.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "config": loqed_integration_config,
            },
        )
        await hass.async_block_till_done()

    json_config = json.loads(loqed_integration_config)
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "LOQED Touch Smart Lock"
    assert result2["data"] == {
        "id": "Foo",
        "ip": json_config["bridge_ip"],
        "host": json_config["bridge_mdns_hostname"],
        "bkey": json_config["bridge_key"],
        "key_id": int(json_config["lock_key_local_id"]),
        "api_key": json_config["lock_key_key"],
        "config": loqed_integration_config,
    }
    mock_lock.getWebhooks.assert_awaited()


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    loqed_integration_config = load_fixture("loqed/integration_config.json")

    with patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "config": loqed_integration_config,
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_wrong_config(hass: HomeAssistant) -> None:
    """Test zeroconf setup errors when provided wrong config."""
    lock_result = json.loads(load_fixture("loqed/status_ok.json"))
    loqed_integration_config = load_fixture("loqed/integration_config.json")

    with patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock_details",
        return_value=lock_result,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                host="127.0.0.1",
                addresses=["127.0.0.1"],
                hostname="LOQED-ffeeddccbbaa.local",
                name="mock_name",
                port=9123,
                properties={},
                type="mock_type",
            ),
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"][CONF_HOST] == "LOQED-ffeeddccbbaa.local"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "config": loqed_integration_config,
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}
