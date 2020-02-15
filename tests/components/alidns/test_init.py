"""Test the AliDNS component."""
from aliyunsdkcore.acs_exception.exceptions import ServerException
from aliyunsdkcore.client import AcsClient
import pytest

from homeassistant.components import alidns
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

ACCESS_ID = ""
ACCESS_KEY = ""
DOMAIN = "xjtu.cn"
SUB_DOMAIN = "www"
UPDATE_INTERVAL = alidns.DEFAULT_INTERVAL
IP_URL = alidns.INTERNET_IP_URL


@pytest.fixture
def setup_alidns(hass, aioclient_mock, monkeypatch):
    """Fixture that sets up alidns."""
    aioclient_mock.get(IP_URL, text="111.222.333.444\n")

    # Any arguments may be passed and will always return our mocked object
    def mock_call_to_aliyun(*args, **kwargs):
        return (
            b'{"TotalCount":1, "DomainRecords": {"Record": [{"RecordId": "9999985"}]}}'
        )

    # apply the monkeypatch for AcsClient.do_action_with_exception to mock_call_to_aliyun
    monkeypatch.setattr(AcsClient, "do_action_with_exception", mock_call_to_aliyun)

    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            alidns.DOMAIN,
            {
                alidns.DOMAIN: {
                    "access_id": ACCESS_ID,
                    "access_key": ACCESS_KEY,
                    "domain": DOMAIN,
                    "sub_domain": SUB_DOMAIN,
                    "scan_interval": UPDATE_INTERVAL,
                }
            },
        )
    )


async def test_setup(hass, aioclient_mock, monkeypatch, caplog):
    """Test setup works if add domain record passes."""
    aioclient_mock.get(IP_URL, text="111.222.333.444\n")

    def mock_call_to_aliyun(*args, **kwargs):
        return b'{"TotalCount":0}'

    monkeypatch.setattr(AcsClient, "do_action_with_exception", mock_call_to_aliyun)

    result = await async_setup_component(
        hass,
        alidns.DOMAIN,
        {
            alidns.DOMAIN: {
                "access_id": ACCESS_ID,
                "access_key": ACCESS_KEY,
                "domain": DOMAIN,
                "sub_domain": SUB_DOMAIN,
                "scan_interval": UPDATE_INTERVAL,
            }
        },
    )
    assert result
    assert aioclient_mock.call_count == 1
    assert "Add Domain Record" in caplog.text

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


async def test_setup_update_record(hass, aioclient_mock, monkeypatch, caplog):
    """Test setup works if update domain record passes."""
    aioclient_mock.get(IP_URL, text="111.222.333.444\n")

    def mock_call_to_aliyun(*args, **kwargs):
        return b'{"TotalCount":1, "DomainRecords": {"Record": [{"RecordId": "9999985", "Value": "222.222.218.111"}]}}'

    monkeypatch.setattr(AcsClient, "do_action_with_exception", mock_call_to_aliyun)

    result = await async_setup_component(
        hass,
        alidns.DOMAIN,
        {
            alidns.DOMAIN: {
                "access_id": ACCESS_ID,
                "access_key": ACCESS_KEY,
                "domain": DOMAIN,
                "sub_domain": SUB_DOMAIN,
                "scan_interval": UPDATE_INTERVAL,
            }
        },
    )
    assert result
    assert aioclient_mock.call_count == 1
    assert "Update Domain Record" in caplog.text


async def test_setup_fails_if_wrong_ip(hass, aioclient_mock):
    """Test setup fails if wrong ip got."""
    aioclient_mock.get(IP_URL, text="ERROR: Invalid update URL ")

    result = await async_setup_component(
        hass,
        alidns.DOMAIN,
        {
            alidns.DOMAIN: {
                "access_id": ACCESS_ID,
                "access_key": ACCESS_KEY,
                "domain": DOMAIN,
                "sub_domain": SUB_DOMAIN,
                "scan_interval": UPDATE_INTERVAL,
            }
        },
    )
    assert not result
    assert aioclient_mock.call_count == 1


async def test_setup_fails_if_exception(hass, aioclient_mock, monkeypatch, caplog):
    """Test setup fails if exception happens."""
    aioclient_mock.get(IP_URL, text="111.222.333.444\n")

    def mock_call_to_aliyun(*args, **kwargs):
        raise ServerException("Error", "Server Error")

    monkeypatch.setattr(AcsClient, "do_action_with_exception", mock_call_to_aliyun)

    result = await async_setup_component(
        hass,
        alidns.DOMAIN,
        {
            alidns.DOMAIN: {
                "access_id": "wrongaccessid",
                "access_key": ACCESS_KEY,
                "domain": DOMAIN,
                "sub_domain": SUB_DOMAIN,
                "scan_interval": UPDATE_INTERVAL,
            }
        },
    )
    assert not result
    assert aioclient_mock.call_count == 1
    assert "Failed to update alidns. Server Exception" in caplog.text
