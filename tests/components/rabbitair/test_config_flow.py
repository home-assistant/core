"""Test the RabbitAir config flow."""

from __future__ import annotations

from collections.abc import Generator
from ipaddress import ip_address
from unittest.mock import MagicMock, Mock, patch

import pytest
from rabbitair import Mode, Model, Speed

from homeassistant import config_entries
from homeassistant.components.rabbitair.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

TEST_HOST = "1.1.1.1"
TEST_NAME = "abcdef1234_123456789012345678"
TEST_TOKEN = "0123456789abcdef0123456789abcdef"
TEST_MAC = "01:23:45:67:89:AB"
TEST_FIRMWARE = "2.3.17"
TEST_HARDWARE = "1.0.0.4"
TEST_UNIQUE_ID = format_mac(TEST_MAC)
TEST_TITLE = "Rabbit Air"

ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address(TEST_HOST),
    ip_addresses=[ip_address(TEST_HOST)],
    port=9009,
    hostname=f"{TEST_NAME}.local.",
    type="_rabbitair._udp.local.",
    name=f"{TEST_NAME}._rabbitair._udp.local.",
    properties={"id": TEST_MAC.replace(":", "")},
)


@pytest.fixture(autouse=True)
def use_mocked_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Mock zeroconf in all tests."""


@pytest.fixture
def rabbitair_connect() -> Generator[None]:
    """Mock connection."""
    with (
        patch("rabbitair.UdpClient.get_info", return_value=get_mock_info()),
        patch("rabbitair.UdpClient.get_state", return_value=get_mock_state()),
    ):
        yield


def get_mock_info(mac: str = TEST_MAC) -> Mock:
    """Return a mock device info instance."""
    mock_info = Mock()
    mock_info.mac = mac
    return mock_info


def get_mock_state(
    model: Model | None = Model.A3,
    main_firmware: str | None = TEST_HARDWARE,
    power: bool | None = True,
    mode: Mode | None = Mode.Auto,
    speed: Speed | None = Speed.Low,
    wifi_firmware: str | None = TEST_FIRMWARE,
) -> Mock:
    """Return a mock device state instance."""
    mock_state = Mock()
    mock_state.model = model
    mock_state.main_firmware = main_firmware
    mock_state.power = power
    mock_state.mode = mode
    mock_state.speed = speed
    mock_state.wifi_firmware = wifi_firmware
    return mock_state


@pytest.mark.usefixtures("rabbitair_connect")
async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.rabbitair.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
                CONF_ACCESS_TOKEN: TEST_TOKEN,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_TITLE
    assert result2["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_ACCESS_TOKEN: TEST_TOKEN,
        CONF_MAC: TEST_MAC,
    }
    assert result2["result"].unique_id == TEST_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error_type", "base_value"),
    [
        (ValueError, "invalid_access_token"),
        (OSError, "invalid_host"),
        (TimeoutError, "timeout_connect"),
        (Exception, "cannot_connect"),
    ],
)
async def test_form_cannot_connect(
    hass: HomeAssistant, error_type: type[Exception], base_value: str
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "rabbitair.UdpClient.get_info",
        side_effect=error_type,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
                CONF_ACCESS_TOKEN: TEST_TOKEN,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": base_value}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.rabbitair.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_HOST,
                CONF_ACCESS_TOKEN: TEST_TOKEN,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("rabbitair_connect")
async def test_zeroconf_discovery(hass: HomeAssistant) -> None:
    """Test zeroconf discovery setup flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=ZEROCONF_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.rabbitair.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: TEST_NAME + ".local",
                CONF_ACCESS_TOKEN: TEST_TOKEN,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_TITLE
    assert result2["data"] == {
        CONF_HOST: TEST_NAME + ".local",
        CONF_ACCESS_TOKEN: TEST_TOKEN,
        CONF_MAC: TEST_MAC,
    }
    assert result2["result"].unique_id == TEST_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=ZEROCONF_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("rabbitair_connect")
async def test_zeroconf_updates_existing_host(hass: HomeAssistant) -> None:
    """Rediscovery updates the stored host for an already configured device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={
            CONF_HOST: "old.local",
            CONF_ACCESS_TOKEN: TEST_TOKEN,
            CONF_MAC: TEST_MAC,
        },
        title=TEST_TITLE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=ZEROCONF_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == TEST_NAME + ".local"


@pytest.mark.usefixtures("rabbitair_connect")
async def test_reconfigure_updates_host(hass: HomeAssistant) -> None:
    """Reconfigure to a new host for the same device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={CONF_HOST: "2.2.2.2", CONF_ACCESS_TOKEN: TEST_TOKEN, CONF_MAC: TEST_MAC},
        title=TEST_TITLE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: TEST_HOST}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == TEST_HOST


async def test_reconfigure_aborts_on_mismatch(hass: HomeAssistant) -> None:
    """Abort reconfigure if the host points to a different device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={CONF_HOST: TEST_HOST, CONF_ACCESS_TOKEN: TEST_TOKEN, CONF_MAC: TEST_MAC},
        title=TEST_TITLE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "rabbitair.UdpClient.get_info", return_value=get_mock_info("AA:BB:CC:DD:EE:FF")
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "2.2.2.2"}
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_device_mismatch"
    assert entry.data[CONF_HOST] == TEST_HOST


async def test_reconfigure_invalid_host_keeps_form(hass: HomeAssistant) -> None:
    """Keep form on validation error and show mapped error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={CONF_HOST: TEST_HOST, CONF_ACCESS_TOKEN: TEST_TOKEN, CONF_MAC: TEST_MAC},
        title=TEST_TITLE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch("rabbitair.UdpClient.get_info", side_effect=OSError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "2.2.2.2"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "invalid_host"}


async def test_reconfigure_unknown_on_exception(hass: HomeAssistant) -> None:
    """Keep form and show unknown if validation raises unexpected exception."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data={CONF_HOST: TEST_HOST, CONF_ACCESS_TOKEN: TEST_TOKEN, CONF_MAC: TEST_MAC},
        title=TEST_TITLE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.rabbitair.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "2.2.2.2"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "unknown"}
    assert entry.data[CONF_HOST] == TEST_HOST
