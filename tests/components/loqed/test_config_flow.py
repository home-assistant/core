"""Test the Loqed config flow."""
import json
from unittest.mock import Mock, patch

from loqedAPI import loqed

from homeassistant import config_entries
from homeassistant.components.loqed.const import DOMAIN
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
                "name": "loqed-abc",
                "internal_url": "http://foo.bar.com",
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
        "name": "loqed-abc",
        "internal_url": "http://foo.bar.com",
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
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "loqed-abc",
                "internal_url": "http://foo.bar.com",
                "config": loqed_integration_config,
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}
