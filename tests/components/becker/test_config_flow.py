"""Tests for the Becker config flow."""
import pytest

from homeassistant.components.becker import const

from tests.async_mock import Mock, patch
from tests.common import MockConfigEntry


@pytest.fixture(name="becker_setup", autouse=True)
def becker_setup_fixture():
    """Mock becker entry setup."""
    with patch("homeassistant.components.becker.async_setup_entry", return_value=True):
        yield


def get_mock_device(device=const.DEFAULT_CONF_USB_STICK_PATH):
    """Return a mock device."""
    mock_device = Mock()
    mock_device.device = device

    return mock_device


async def test_user_input_successful(hass):
    """Test a successful connection."""
    flow = await hass.config_entries.flow.async_init(
        "becker", context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {const.CONF_DEVICE: const.DEFAULT_CONF_USB_STICK_PATH}
    )
    assert result["type"] == "create_entry"
    assert result["result"].data == {
        const.CONF_DEVICE: const.DEFAULT_CONF_USB_STICK_PATH
    }


async def test_user_already_configured(hass):
    """Test duplicated config."""
    flow = await hass.config_entries.flow.async_init(
        "becker", context={"source": "user"}
    )

    MockConfigEntry(
        domain="becker",
        unique_id="aabbccddeeff",
        data={"device": const.DEFAULT_CONF_USB_STICK_PATH},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {const.CONF_DEVICE: const.DEFAULT_CONF_USB_STICK_PATH}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "one_instance_only"


async def test_import_with_no_config(hass):
    """Test importing a host without an existing config file."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": "import"},
        data={const.CONF_DEVICE: const.DEFAULT_CONF_USB_STICK_PATH},
    )
    assert result["type"] == "create_entry"
    assert result["data"][const.CONF_DEVICE] == const.DEFAULT_CONF_USB_STICK_PATH


async def test_import_already_configured(hass):
    """Test if a import flow aborts if device is already configured."""
    MockConfigEntry(
        domain="becker",
        unique_id="aabbccddeeff",
        data={"device": const.DEFAULT_CONF_USB_STICK_PATH},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": "import"},
        data={
            const.CONF_DEVICE: const.DEFAULT_CONF_USB_STICK_PATH,
            "properties": {"id": "aa:bb:cc:dd:ee:ff"},
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
