"""Test the Route53 component."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiohttp import ClientError
import pytest

from homeassistant.components.route53.const import (
    CONF_ACCESS_KEY_ID,
    CONF_RECORDS,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_TTL,
    DOMAIN,
    INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_entry(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup and unload of entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1", "test2"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    aioclient_mock.get("https://api.ipify.org/", text="1.2.3.4")
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "update_records")

    # Test unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # The service remains registered globally across config entries.
    # It is not removed when a single entry unloads.
    assert hass.services.has_service(DOMAIN, "update_records")


async def test_setup_with_yaml_triggers_import(hass: HomeAssistant) -> None:
    """Test setup with yaml triggers import."""
    with (
        patch("homeassistant.components.route53.async_setup_entry", return_value=True),
        patch.object(
            hass.config_entries.flow,
            "async_init",
            return_value={"type": FlowResultType.CREATE_ENTRY},
        ) as mock_init,
    ):
        await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_ACCESS_KEY_ID: "test-key",
                    CONF_SECRET_ACCESS_KEY: "test-secret",
                    CONF_ZONE: "test-zone",
                    CONF_DOMAIN: "example.com",
                    CONF_RECORDS: ["test1"],
                    CONF_TTL: DEFAULT_TTL,
                }
            },
        )
        await hass.async_block_till_done()

    mock_init.assert_called_once()


async def test_update_records_service(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the update_records service."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1", "."],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    aioclient_mock.get("https://api.ipify.org/", text="1.2.3.4")
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Reset mock to test service call separately
    mock_boto3_client.return_value.change_resource_record_sets.reset_mock()

    aioclient_mock.clear_requests()
    aioclient_mock.get("https://api.ipify.org/", text="5.6.7.8")
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        await hass.services.async_call(DOMAIN, "update_records", blocking=True)
        await hass.async_block_till_done()

    mock_boto3_client.return_value.change_resource_record_sets.assert_called_once_with(
        HostedZoneId="test-zone",
        ChangeBatch={
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "test1.example.com",
                        "Type": "A",
                        "TTL": DEFAULT_TTL,
                        "ResourceRecords": [{"Value": "5.6.7.8"}],
                    },
                },
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": "example.com",
                        "Type": "A",
                        "TTL": DEFAULT_TTL,
                        "ResourceRecords": [{"Value": "5.6.7.8"}],
                    },
                },
            ]
        },
    )


async def test_update_ipify_fails(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test when ipify request fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    aioclient_mock.get("https://api.ipify.org/", exc=ClientError())
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY

    # Boto3 shouldn't be called if IP cannot be fetched
    mock_boto3_client.return_value.change_resource_record_sets.assert_not_called()


async def test_update_boto3_fails(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test when boto3 request returns non-200."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    mock_boto3_client.return_value.change_resource_record_sets.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 400}
    }

    aioclient_mock.get("https://api.ipify.org/", text="1.2.3.4")
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "HTTPStatusCode': 400" in caplog.text


async def test_service_update_ipify_fails(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test when ipify request fails during service call."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    aioclient_mock.get("https://api.ipify.org/", text="1.2.3.4")
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get("https://api.ipify.org/", exc=ClientError())
    with (
        patch(
            "homeassistant.components.route53.boto3.client",
            return_value=mock_boto3_client.return_value,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(DOMAIN, "update_records", blocking=True)


async def test_service_update_boto3_fails(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test when boto3 request returns non-200 during service call."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    aioclient_mock.get("https://api.ipify.org/", text="1.2.3.4")
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_boto3_client.return_value.change_resource_record_sets.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 400}
    }

    aioclient_mock.clear_requests()
    aioclient_mock.get("https://api.ipify.org/", text="1.2.3.4")
    with (
        patch(
            "homeassistant.components.route53.boto3.client",
            return_value=mock_boto3_client.return_value,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(DOMAIN, "update_records", blocking=True)


async def test_periodic_update(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test records are updated on the tracked interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY_ID: "test-key",
            CONF_SECRET_ACCESS_KEY: "test-secret",
            CONF_ZONE: "test-zone",
            CONF_DOMAIN: "example.com",
            CONF_RECORDS: ["test1"],
            CONF_TTL: DEFAULT_TTL,
        },
    )
    entry.add_to_hass(hass)

    aioclient_mock.get("https://api.ipify.org/", text="1.2.3.4")
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_boto3_client.return_value.change_resource_record_sets.reset_mock()

        async_fire_time_changed(
            hass, dt_util.utcnow() + INTERVAL + timedelta(seconds=1)
        )
        await hass.async_block_till_done()

    mock_boto3_client.return_value.change_resource_record_sets.assert_called_once()

    # A failure on the interval is logged but leaves the entry loaded
    aioclient_mock.clear_requests()
    aioclient_mock.get("https://api.ipify.org/", exc=ClientError())
    with patch(
        "homeassistant.components.route53.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + 2 * INTERVAL + timedelta(seconds=1)
        )
        await hass.async_block_till_done()

    assert "Unable to reach the ipify service" in caplog.text
    assert entry.state is ConfigEntryState.LOADED


async def test_yaml_import_failure_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_boto3_client: MagicMock,
) -> None:
    """Test a failed YAML import raises a repair issue."""
    mock_boto3_client.return_value.get_hosted_zone.side_effect = Exception

    with patch(
        "homeassistant.components.route53.config_flow.boto3.client",
        return_value=mock_boto3_client.return_value,
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_ACCESS_KEY_ID: "test-key",
                    CONF_SECRET_ACCESS_KEY: "test-secret",
                    CONF_ZONE: "test-zone",
                    CONF_DOMAIN: "example.com",
                    CONF_RECORDS: ["test1"],
                    CONF_TTL: DEFAULT_TTL,
                }
            },
        )
        await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_unknown"
    )
