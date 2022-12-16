"""pytest helpers for VeSync component tests."""
import pytest

from homeassistant.components.vesync.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture()
async def setup_platform(hass):
    """Set up the ecobee platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "ABC123",
            CONF_PASSWORD: "EFG456",
        },
    )
    mock_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock):
    """Fixture to provide a requests mocker."""
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/user/login",
        text=load_fixture("vesync/vesync-login.json"),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices",
        text=load_fixture("vesync/vesync-devices.json"),
    )
    requests_mock.get(
        "https://smartapi.vesync.com/v1/device/outlet/detail",
        text=load_fixture("vesync/outlet-detail.json"),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/dimmer/v1/device/devicedetail",
        text=load_fixture("vesync/dimmer-detail.json"),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/SmartBulb/v1/device/devicedetail",
        text=load_fixture("vesync/device-detail.json"),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/bypass",
        text=load_fixture("vesync/device-detail.json"),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v2/deviceManaged/bypassV2",
        text=load_fixture("vesync/device-detail.json"),
    )
    requests_mock.post(
        "https://smartapi.vesync.com/131airPurifier/v1/device/deviceDetail",
        text=load_fixture("vesync/purifier-detail.json"),
    )
