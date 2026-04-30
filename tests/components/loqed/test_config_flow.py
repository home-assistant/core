"""Test the Loqed config flow."""

from ipaddress import ip_address
import json
from unittest.mock import Mock, patch

import aiohttp
from loqedAPI import loqed

from homeassistant import config_entries
from homeassistant.components.loqed.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

zeroconf_data = ZeroconfServiceInfo(
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
    lock_result = json.loads(await async_load_fixture(hass, "status_ok.json", DOMAIN))

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
    all_locks_response = json.loads(
        await async_load_fixture(hass, "get_all_locks.json", DOMAIN)
    )

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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "eyadiuyfasiuasf",
            },
        )
        await hass.async_block_till_done()
    found_lock = all_locks_response["data"][0]

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MyLock"
    assert result["data"] == {
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

    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    webhook_id = "Webhook_ID"
    all_locks_response = json.loads(
        await async_load_fixture(hass, "get_all_locks.json", DOMAIN)
    )
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MyLock"
    assert result["data"] == {
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


async def test_create_entry_user_with_pick_lock(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we can create a lock via manual entry when multiple locks exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    webhook_id = "Webhook_ID"
    all_locks_response = json.loads(
        await async_load_fixture(hass, "get_all_locks.json", DOMAIN)
    )
    second_lock = all_locks_response["data"][0].copy()
    second_lock["id"] = "Bar"
    second_lock["name"] = "MyOtherLock"
    all_locks_response["data"].append(second_lock)

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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick_lock"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"lock_id": second_lock["id"]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == second_lock["name"]
    assert result["data"] == {
        "id": second_lock["id"],
        "lock_key_key": second_lock["key_secret"],
        "bridge_key": second_lock["bridge_key"],
        "lock_key_local_id": second_lock["local_id"],
        "bridge_mdns_hostname": second_lock["bridge_hostname"],
        "bridge_ip": second_lock["bridge_ip"],
        "name": second_lock["name"],
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_recover_after_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we can recover from a connection error and create an entry."""
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
        error_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )
        await hass.async_block_till_done()

    assert error_result["type"] is FlowResultType.FORM
    assert error_result["errors"] == {"base": "cannot_connect"}

    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    webhook_id = "Webhook_ID"
    all_locks_response = json.loads(
        await async_load_fixture(hass, "get_all_locks.json", DOMAIN)
    )
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
    ):
        success_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )
        await hass.async_block_till_done()

    assert success_result["type"] is FlowResultType.CREATE_ENTRY
    assert success_result["title"] == "MyLock"
    assert success_result["data"] == {
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


async def test_no_locks(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle a situation where the account has no locks."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
        return_value={"data": []},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_locks"}


async def test_invalid_auth_when_lock_not_found(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle a situation where the lock is absent from the cloud API response."""
    lock_result = json.loads(await async_load_fixture(hass, "status_ok.json", DOMAIN))

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

    with patch(
        "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
        return_value={"data": []},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect_zeroconf_cloud_api_error(
    hass: HomeAssistant,
) -> None:
    """Test we handle a cloud API error during zeroconf validate_input."""
    lock_result = json.loads(await async_load_fixture(hass, "status_ok.json", DOMAIN))

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

    with patch(
        "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
        side_effect=aiohttp.ClientError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_cannot_connect_when_lock_not_reachable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle a situation where the lock is not reachable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    all_locks_response = json.loads(
        await async_load_fixture(hass, "get_all_locks.json", DOMAIN)
    )

    with (
        patch(
            "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
            return_value=all_locks_response,
        ),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock", side_effect=aiohttp.ClientError
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "eyadiuyfasiuasf"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
