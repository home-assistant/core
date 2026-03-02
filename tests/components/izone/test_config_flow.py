"""Tests for iZone."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.izone.const import DISPATCH_CONTROLLER_DISCOVERED, IZONE
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


@pytest.fixture
def mock_disco() -> Mock:
    """Mock discovery service."""
    disco = Mock()
    disco.pi_disco = Mock()
    disco.pi_disco.controllers = {}
    return disco


def _mock_start_discovery(hass: HomeAssistant, mock_disco: Mock) -> Callable[..., Mock]:
    def do_disovered(*args: Any) -> Mock:
        async_dispatcher_send(hass, DISPATCH_CONTROLLER_DISCOVERED, True)
        return mock_disco

    return do_disovered


async def test_not_found(hass: HomeAssistant, mock_disco: Mock) -> None:
    """Test not finding iZone controller via auto-discovery."""

    with (
        patch(
            "homeassistant.components.izone.config_flow.async_start_discovery_service"
        ) as start_disco,
        patch(
            "homeassistant.components.izone.config_flow.async_stop_discovery_service",
            return_value=None,
        ) as stop_disco,
    ):
        start_disco.side_effect = _mock_start_discovery(hass, mock_disco)
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        # User form with optional host field
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Submit with blank host to trigger auto-discovery
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        await hass.async_block_till_done()

    stop_disco.assert_called_once()


async def test_found(hass: HomeAssistant, mock_disco: Mock) -> None:
    """Test finding iZone controller via auto-discovery."""
    mock_disco.pi_disco.controllers["blah"] = object()

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.izone.config_flow.async_start_discovery_service"
        ) as start_disco,
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        start_disco.side_effect = _mock_start_discovery(hass, mock_disco)
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        # User form with optional host field
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Submit with blank host to trigger auto-discovery
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        # Discovery confirmation form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "discover"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {}

        await hass.async_block_till_done()

    mock_setup.assert_called_once()


async def test_manual_ip_success(hass: HomeAssistant) -> None:
    """Test manually configuring an iZone controller by IP address."""
    mock_controller = Mock()
    mock_controller.device_uid = "000013170"

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.izone.config_flow.async_get_device_uid",
            return_value="000013170",
        ),
        patch(
            "homeassistant.components.izone.async_add_controller_by_ip",
            return_value=mock_controller,
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.2.100"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "iZone 000013170"
        assert result["data"] == {CONF_HOST: "192.168.2.100"}

        await hass.async_block_till_done()

    mock_setup.assert_called_once()


async def test_manual_ip_cannot_connect(hass: HomeAssistant) -> None:
    """Test manually configuring with an unreachable IP address."""
    with patch(
        "homeassistant.components.izone.config_flow.async_get_device_uid",
        side_effect=ConnectionError("Unable to connect"),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.2.100"}
        )

        # Should show form again with error
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_manual_ip_already_configured(hass: HomeAssistant) -> None:
    """Test manually configuring an already-configured device."""
    entry = MockConfigEntry(
        domain=IZONE,
        title="iZone 000013170",
        data={CONF_HOST: "192.168.2.50"},
        unique_id="000013170",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.izone.config_flow.async_get_device_uid",
        return_value="000013170",
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.2.100"}
        )

        # Should abort because unique_id already exists (IP gets updated)
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

        # Verify the host was updated
        assert entry.data[CONF_HOST] == "192.168.2.100"


async def test_single_instance_allowed_when_entry_exists(
    hass: HomeAssistant,
) -> None:
    """Test that auto-discovery aborts when a discovery entry already exists."""
    entry = MockConfigEntry(
        domain=IZONE,
        title="iZone",
        data={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        IZONE, context={"source": config_entries.SOURCE_USER}
    )

    # User form should still show (allows adding manual IP)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit blank host to trigger auto-discovery
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Should abort because a discovery entry already exists
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_import_flow(hass: HomeAssistant, mock_disco: Mock) -> None:
    """Test import from configuration.yaml."""
    mock_disco.pi_disco.controllers["blah"] = object()

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.izone.config_flow.async_start_discovery_service"
        ) as start_disco,
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        start_disco.side_effect = _mock_start_discovery(hass, mock_disco)
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_IMPORT}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "iZone"
        assert result["data"] == {}

        await hass.async_block_till_done()

    mock_setup.assert_called_once()


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test import aborts when already configured."""
    entry = MockConfigEntry(
        domain=IZONE,
        title="iZone",
        data={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        IZONE, context={"source": config_entries.SOURCE_IMPORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_import_no_devices(hass: HomeAssistant, mock_disco: Mock) -> None:
    """Test import aborts when no devices found."""
    with (
        patch(
            "homeassistant.components.izone.config_flow.async_start_discovery_service"
        ) as start_disco,
        patch(
            "homeassistant.components.izone.config_flow.async_stop_discovery_service",
            return_value=None,
        ),
    ):
        start_disco.side_effect = _mock_start_discovery(hass, mock_disco)
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_IMPORT}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test unloading a config entry."""
    from . import setup_controller, setup_integration

    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    assert mock_config_entry.state is config_entries.ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_setup_entry_with_host(hass: HomeAssistant) -> None:
    """Test setup entry when host is configured."""
    mock_controller = Mock()
    mock_controller.device_uid = "000013170"

    entry = MockConfigEntry(
        domain=IZONE,
        title="iZone 000013170",
        data={CONF_HOST: "192.168.2.100"},
        unique_id="000013170",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.izone.async_add_controller_by_ip",
            return_value=mock_controller,
        ) as mock_add,
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_add.assert_called_once_with(hass, "192.168.2.100", "000013170")
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_setup_entry_with_host_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test setup entry raises ConfigEntryNotReady on connection error."""
    entry = MockConfigEntry(
        domain=IZONE,
        title="iZone 000013170",
        data={CONF_HOST: "192.168.2.100"},
        unique_id="000013170",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.izone.async_add_controller_by_ip",
            side_effect=ConnectionError("Unable to connect"),
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
