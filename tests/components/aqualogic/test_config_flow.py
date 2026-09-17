"""Tests for the AquaLogic config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.aqualogic.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aqualogic.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.mark.usefixtures("mock_aqualogic_device")
async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AquaLogic"
    assert result["data"] == {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}
    mock_setup_entry.assert_called_once()


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_aqualogic_device: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle cannot connect error and allow retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_aqualogic_device.return_value.connect.side_effect = OSError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_aqualogic_device.return_value.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_device(
    hass: HomeAssistant,
    mock_aqualogic_device: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle a device that does not speak the AquaLogic protocol."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_aqualogic_device.return_value.process.side_effect = None
    with patch("homeassistant.components.aqualogic.config_flow._PROBE_TIMEOUT", 0):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_device"}

    def _fake_process(callback: object) -> None:
        callback(mock_aqualogic_device.return_value)

    mock_aqualogic_device.return_value.process.side_effect = _fake_process

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if the host/port is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_aqualogic_device")
async def test_import_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test importing from configuration.yaml creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AquaLogic"
    assert result["data"] == {CONF_HOST: "1.2.3.4", CONF_PORT: 8899}
    mock_setup_entry.assert_called_once()


async def test_import_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test we abort the import if we cannot connect."""
    with patch(
        "homeassistant.components.aqualogic.config_flow.AquaLogic"
    ) as mock_al_class:
        mock_al_class.return_value.connect.side_effect = OSError
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_invalid_device(hass: HomeAssistant) -> None:
    """Test we abort the import if the device does not speak the AquaLogic protocol."""
    with (
        patch("homeassistant.components.aqualogic.config_flow.AquaLogic"),
        patch("homeassistant.components.aqualogic.config_flow._PROBE_TIMEOUT", 0),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort the import if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.2.3.4", CONF_PORT: 8899},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
