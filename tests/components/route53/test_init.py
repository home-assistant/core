"""Test the route53 component."""
import pytest

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.components import route53
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from requests_mock import Mocker
from tests.common import async_fire_time_changed
from unittest.mock import patch, MagicMock

IP = "172.13.0.1"

AWS_ACCESS_KEY_ID = "access_key_id"
AWS_SECRET_ACCESS_KEY = "secret_access_key"

URL = "https://api.ipify.org/"
TTL = 300
ZONE = "zone"
DOMAIN = "domain.example.com"
RECORDS = ["home"]


@pytest.fixture(name="boto3")
def fixture_boto3() -> None:
    """Patch boto3 for mocks."""
    with patch("homeassistant.components.route53.boto3") as boto3_mock:
        yield boto3_mock


async def test_setup(
    hass: HomeAssistant,
    requests_mock: Mocker,
    boto3: MagicMock,
) -> None:
    """Test that set-up adds the cron task."""
    requests_mock.get(URL, text=IP)
    await _setup_component(hass)

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=route53.INTERVAL.seconds + 1)
    )

    await hass.async_block_till_done()
    assert requests_mock.call_count == 1


async def test_update(
    hass: HomeAssistant,
    requests_mock: Mocker,
    boto3: MagicMock,
) -> None:
    """Test update_records sends the correct values to route53."""
    requests_mock.get(URL, text=IP)
    await _setup_component(hass)

    await hass.services.async_call(
        route53.DOMAIN,
        "update_records",
        blocking=True,
    )

    assert requests_mock.call_count == 1

    boto3.client.assert_called_once_with(
        "route53",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

    route53_client = boto3.client.return_value
    route53_client.change_resource_record_sets.assert_called_once_with(
        HostedZoneId=ZONE,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": f"{RECORDS[0]}.{DOMAIN}",
                        "Type": "A",
                        "TTL": TTL,
                        "ResourceRecords": [{"Value": IP}],
                    },
                },
            ],
        },
    )


async def _setup_component(hass: HomeAssistant) -> None:
    """Sets-up the route53 component for multiple tests."""
    await async_setup_component(
        hass,
        route53.DOMAIN,
        {
            route53.DOMAIN: {
                "aws_access_key_id": AWS_ACCESS_KEY_ID,
                "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
                "zone": ZONE,
                "domain": DOMAIN,
                "records": RECORDS,
            },
        },
    )
