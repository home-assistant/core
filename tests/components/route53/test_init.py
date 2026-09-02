"""Test the Route53 component."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from aiohttp import ClientError
import botocore.exceptions
import pytest

from homeassistant.components.route53.const import (
    CONF_ACCESS_KEY_ID,
    CONF_RECORDS,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_TTL,
    DOMAIN,
    INTERVAL,
)
from homeassistant.components.route53.helpers import IPIFY_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

SUCCESS = {"ResponseMetadata": {"HTTPStatusCode": 200}}

YAML_CONFIG = {
    CONF_ACCESS_KEY_ID: "test-key",
    CONF_SECRET_ACCESS_KEY: "test-secret",
    CONF_ZONE: "test-zone",
    CONF_DOMAIN: "example.com",
    CONF_RECORDS: ["test1"],
    CONF_TTL: DEFAULT_TTL,
}

pytestmark = pytest.mark.usefixtures("mock_boto3_client", "mock_ipify")


async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, "update_records")

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    # The action stays registered; it is shared by every loaded entry
    assert hass.services.has_service(DOMAIN, "update_records")


async def test_action_updates_records(
    hass: HomeAssistant,
    mock_boto3_client: MagicMock,
    mock_ipify: AiohttpClientMocker,
) -> None:
    """Test the update_records action publishes the current address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-zone_example.com",
        data={**YAML_CONFIG, CONF_RECORDS: ["test1", "."]},
    )
    await setup_integration(hass, entry)

    mock_boto3_client.change_resource_record_sets.reset_mock()
    mock_ipify.clear_requests()
    mock_ipify.get(IPIFY_URL, text="5.6.7.8")

    await hass.services.async_call(DOMAIN, "update_records", blocking=True)
    await hass.async_block_till_done()

    mock_boto3_client.change_resource_record_sets.assert_called_once_with(
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


async def test_records_are_updated_on_the_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_boto3_client: MagicMock,
    mock_ipify: AiohttpClientMocker,
) -> None:
    """Test the records are refreshed on the tracked interval."""
    await setup_integration(hass, mock_config_entry)
    mock_boto3_client.change_resource_record_sets.reset_mock()

    async_fire_time_changed(hass, dt_util.utcnow() + INTERVAL + timedelta(seconds=1))
    await hass.async_block_till_done()

    mock_boto3_client.change_resource_record_sets.assert_called_once()

    # A failing refresh leaves the entry loaded so the next one can succeed
    mock_ipify.clear_requests()
    mock_ipify.get(IPIFY_URL, exc=ClientError())

    async_fire_time_changed(
        hass, dt_util.utcnow() + 2 * INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(ClientError(), id="client_error"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_setup_retries_when_ip_lookup_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipify: AiohttpClientMocker,
    exc: Exception,
) -> None:
    """Test the entry retries when the public address cannot be determined."""
    mock_ipify.clear_requests()
    mock_ipify.get(IPIFY_URL, exc=exc)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("side_effect", "response"),
    [
        pytest.param(botocore.exceptions.BotoCoreError(), SUCCESS, id="botocore_error"),
        pytest.param(
            botocore.exceptions.ClientError(
                {"Error": {"Code": "AccessDenied"}}, "ChangeResourceRecordSets"
            ),
            SUCCESS,
            id="client_error",
        ),
        pytest.param(
            None,
            {"ResponseMetadata": {"HTTPStatusCode": 400}},
            id="unsuccessful_response",
        ),
    ],
)
async def test_setup_retries_when_route53_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_boto3_client: MagicMock,
    side_effect: Exception | None,
    response: dict[str, dict[str, int]],
) -> None:
    """Test the entry retries when the records cannot be published."""
    mock_boto3_client.change_resource_record_sets.side_effect = side_effect
    mock_boto3_client.change_resource_record_sets.return_value = response

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_client_cannot_be_created(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry retries when boto3 cannot build a client."""
    with patch(
        "homeassistant.components.route53.helpers.boto3.client",
        side_effect=botocore.exceptions.ConfigParseError(path="/etc/aws/config"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_action_reports_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_boto3_client: MagicMock,
) -> None:
    """Test the action names the entry that could not be updated."""
    await setup_integration(hass, mock_config_entry)

    mock_boto3_client.change_resource_record_sets.side_effect = (
        botocore.exceptions.BotoCoreError()
    )

    with pytest.raises(HomeAssistantError, match="example.com"):
        await hass.services.async_call(DOMAIN, "update_records", blocking=True)
