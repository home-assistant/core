"""Test the IKEA Idasen Desk config flow."""

from unittest.mock import ANY, MagicMock, patch

from bleak.exc import BleakError
from idasen_ha.errors import AuthFailedError
import pytest

from homeassistant import config_entries
from homeassistant.components.idasen_desk.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import IDASEN_DISCOVERY_INFO, NOT_IDASEN_DISCOVERY_INFO

from tests.common import MockConfigEntry


async def test_user_step_success(hass: HomeAssistant, mock_desk_api: MagicMock) -> None:
    """Test user step success path."""
    with patch(
        "homeassistant.components.idasen_desk.config_flow.async_discovered_service_info",
        return_value=[NOT_IDASEN_DISCOVERY_INFO, IDASEN_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.idasen_desk.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == IDASEN_DISCOVERY_INFO.name
    assert result2["data"] == {
        CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
    }
    assert result2["result"].unique_id == IDASEN_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_replaces_ignored_device(
    hass: HomeAssistant, mock_desk_api: MagicMock
) -> None:
    """Test user step replaces ignored devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=IDASEN_DISCOVERY_INFO.address,
        source=config_entries.SOURCE_IGNORE,
        data={CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.idasen_desk.config_flow.async_discovered_service_info",
        return_value=[NOT_IDASEN_DISCOVERY_INFO, IDASEN_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.idasen_desk.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == IDASEN_DISCOVERY_INFO.name
    assert result2["data"] == {
        CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
    }
    assert result2["result"].unique_id == IDASEN_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_no_devices_found(hass: HomeAssistant) -> None:
    """Test user step with no devices found."""
    with patch(
        "homeassistant.components.idasen_desk.config_flow.async_discovered_service_info",
        return_value=[NOT_IDASEN_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_no_new_devices_found(hass: HomeAssistant) -> None:
    """Test user step with only existing devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
        },
        unique_id=IDASEN_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.idasen_desk.config_flow.async_discovered_service_info",
        return_value=[IDASEN_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "cannot_connect"),
        (BleakError, "cannot_connect"),
        (AuthFailedError, "auth_failed"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_step_cannot_connect(
    hass: HomeAssistant,
    mock_desk_api: MagicMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step with a cannot connect error."""
    with patch(
        "homeassistant.components.idasen_desk.config_flow.async_discovered_service_info",
        return_value=[IDASEN_DISCOVERY_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    default_connect_side_effect = mock_desk_api.connect.side_effect
    mock_desk_api.connect.side_effect = exception

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": expected_error}

    mock_desk_api.connect.side_effect = default_connect_side_effect
    with patch(
        "homeassistant.components.idasen_desk.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == IDASEN_DISCOVERY_INFO.name
    assert result3["data"] == {
        CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
    }
    assert result3["result"].unique_id == IDASEN_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_step_success(
    hass: HomeAssistant, mock_desk_api: MagicMock
) -> None:
    """Test bluetooth step success path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=IDASEN_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.idasen_desk.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == IDASEN_DISCOVERY_INFO.name
    assert result2["data"] == {
        CONF_ADDRESS: IDASEN_DISCOVERY_INFO.address,
    }
    assert result2["result"].unique_id == IDASEN_DISCOVERY_INFO.address
    assert len(mock_setup_entry.mock_calls) == 1
    mock_desk_api.connect.assert_called_with(ANY, retry=False)
