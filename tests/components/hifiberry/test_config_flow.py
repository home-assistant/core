"""Test the HiFiBerry config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from aiohifiberry import AudioControlError

from homeassistant import config_entries
from homeassistant.components.hifiberry.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

TEST_CONNECTION = {CONF_HOST: "hifiberry.local", CONF_PORT: DEFAULT_PORT}

TEST_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="hifiberry.local.",
    name="HiFiBerry._mpd._tcp.local.",
    port=6600,
    properties={},
    type="_mpd._tcp.local.",
)


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "hifiberry.local"
    assert result2["data"] == TEST_CONNECTION
    assert result2["result"].unique_id == "hifiberry.local"
    mock_audiocontrol_client.async_validate.assert_awaited_once()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_audiocontrol_client: MagicMock
) -> None:
    """Test we handle connection errors."""
    mock_audiocontrol_client.async_validate.side_effect = AudioControlError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistant, mock_audiocontrol_client: MagicMock
) -> None:
    """Test we handle unexpected errors."""
    mock_audiocontrol_client.async_validate.side_effect = RuntimeError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_duplicate_updates_existing_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test a duplicate host aborts and updates the existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="hifiberry.local",
        data={CONF_HOST: "old.local", CONF_PORT: 81},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_CONNECTION,
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert entry.data == TEST_CONNECTION
    mock_audiocontrol_client.async_validate.assert_awaited_once()
    assert len(mock_setup_entry.mock_calls) == 0


async def test_zeroconf(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=TEST_DISCOVERY
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "hifiberry.local"
    assert result2["data"] == TEST_CONNECTION
    assert result2["result"].unique_id == "hifiberry.local"
    mock_audiocontrol_client.async_validate.assert_awaited_once()
    assert len(mock_setup_entry.mock_calls) == 1
