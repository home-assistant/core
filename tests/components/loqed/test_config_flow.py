"""Test the Loqed config flow."""

from ipaddress import ip_address
import json
from unittest.mock import Mock, patch

import aiohttp
from loqedAPI import loqed

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.loqed.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_NAME, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

zeroconf_data = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("192.168.12.34"),
    ip_addresses=[ip_address("192.168.12.34")],
    hostname="LOQED-ffeeddccbbaa.local",
    name="mock_name",
    port=9123,
    properties={},
    type="mock_type",
)


async def test_create_entry_zeroconf(hass: HomeAssistant) -> None:
    """Test we get can create a lock via zeroconf."""
    lock_result = json.loads(load_fixture("loqed/status_ok.json"))

    with patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock_details",
        return_value=lock_result,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf_data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    webhook_id = "Webhook_ID"
    all_locks_response = json.loads(load_fixture("loqed/get_all_locks.json"))

    with (
        patch(
            "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
            return_value=all_locks_response,
        ),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock",
            return_value=mock_lock,
        ),
        patch(
            "homeassistant.components.loqed.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value=webhook_id,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "eyadiuyfasiuasf",
            },
        )
        await hass.async_block_till_done()
    found_lock = all_locks_response["data"][0]

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "LOQED Touch Smart Lock"
    assert result2["data"] == {
        "id": "Foo",
        "lock_key_key": found_lock["key_secret"],
        "bridge_key": found_lock["bridge_key"],
        "lock_key_local_id": found_lock["local_id"],
        "bridge_mdns_hostname": found_lock["bridge_hostname"],
        "bridge_ip": found_lock["bridge_ip"],
        "name": found_lock["name"],
        CONF_WEBHOOK_ID: webhook_id,
        CONF_API_TOKEN: "eyadiuyfasiuasf",
    }
    mock_lock.getWebhooks.assert_awaited()


async def test_create_entry_user(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we can create a lock via manual entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    lock_result = json.loads(load_fixture("loqed/status_ok.json"))
    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    webhook_id = "Webhook_ID"
    all_locks_response = json.loads(load_fixture("loqed/get_all_locks.json"))
    found_lock = all_locks_response["data"][0]

    with (
        patch(
            "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
            return_value=all_locks_response,
        ),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock",
            return_value=mock_lock,
        ),
        patch(
            "homeassistant.components.loqed.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.webhook.async_generate_id",
            return_value=webhook_id,
        ),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_result
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf", CONF_NAME: "MyLock"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "LOQED Touch Smart Lock"
    assert result2["data"] == {
        "id": "Foo",
        "lock_key_key": found_lock["key_secret"],
        "bridge_key": found_lock["bridge_key"],
        "lock_key_local_id": found_lock["local_id"],
        "bridge_mdns_hostname": found_lock["bridge_hostname"],
        "bridge_ip": found_lock["bridge_ip"],
        "name": found_lock["name"],
        CONF_WEBHOOK_ID: webhook_id,
        CONF_API_TOKEN: "eyadiuyfasiuasf",
    }
    mock_lock.getWebhooks.assert_awaited()


async def test_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf", CONF_NAME: "MyLock"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_invalid_auth_when_lock_not_found(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle a situation where the user enters an invalid lock name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    all_locks_response = json.loads(load_fixture("loqed/get_all_locks.json"))

    with patch(
        "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
        return_value=all_locks_response,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf", CONF_NAME: "MyLock2"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect_when_lock_not_reachable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle a situation where the user enters an invalid lock name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    all_locks_response = json.loads(load_fixture("loqed/get_all_locks.json"))

    with (
        patch(
            "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
            return_value=all_locks_response,
        ),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock", side_effect=aiohttp.ClientError
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf", CONF_NAME: "MyLock"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
