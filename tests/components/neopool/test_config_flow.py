"""Test the NeoPool config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.neopool import config_flow
from homeassistant.components.neopool.config_flow import NeoPoolConfigFlow
from homeassistant.components.neopool.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST, MOCK_PORT, MOCK_SERIAL

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_socket_connection")

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
}


async def test_user_flow(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a happy-path config flow creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pool"
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["result"].unique_id == f"neopool_{MOCK_SERIAL}"
    assert mock_setup_entry.call_count == 1


async def test_user_flow_falls_back_to_brand_name_on_translation_error(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """If translation lookup fails, the entry title falls back to the brand name."""
    with patch(
        "homeassistant.components.neopool.config_flow.ha_translation.async_get_translations",
        side_effect=RuntimeError("translations unavailable"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NeoPool"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow surfaces a cannot_connect error and recovers."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            config_flow,
            "is_host_port_open",
            AsyncMock(return_value=False),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_read_modbus(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow surfaces cannot_read_modbus when serial probe fails."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            config_flow,
            "async_get_device_serial",
            AsyncMock(return_value=None),
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "cannot_read_modbus"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Test config flow aborts when the same device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_happy_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A reconfigure flow updates host/port and reloads the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.50",
            CONF_PORT: 1502,
            "unit_id": 2,
            "modbus_framer": "tcp",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.0.2.50"
    assert mock_config_entry.data[CONF_PORT] == 1502

    while mock_config_entry.state is not ConfigEntryState.LOADED:
        await hass.async_block_till_done()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A reconfigure flow with an unreachable host shows the cannot_connect error."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config_flow, "is_host_port_open", AsyncMock(return_value=False))
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.0.2.99",
                CONF_PORT: 502,
                "unit_id": 1,
                "modbus_framer": "tcp",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "cannot_connect"}


async def test_reconfigure_flow_serial_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A reconfigure that targets a different physical controller is rejected."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            config_flow,
            "async_get_device_serial",
            AsyncMock(return_value="9999999999"),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.0.2.50",
                CONF_PORT: 502,
                "unit_id": 1,
                "modbus_framer": "tcp",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "serial_mismatch"}


async def test_reconfigure_flow_cannot_read_modbus(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """If the serial probe fails on reconfigure, we surface cannot_read_modbus."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            config_flow,
            "async_get_device_serial",
            AsyncMock(return_value=None),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.0.2.50",
                CONF_PORT: 502,
                "unit_id": 1,
                "modbus_framer": "tcp",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "cannot_read_modbus"}


async def test_default_name_translation_failure_falls_back(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
) -> None:
    """If the translation lookup explodes, _async_get_default_name returns the literal default."""
    with patch(
        "homeassistant.helpers.translation.async_get_translations",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM


async def test_reconfigure_flow_aborts_when_entry_id_missing(
    hass: HomeAssistant,
) -> None:
    """async_step_reconfigure aborts when context has no entry_id."""
    flow = NeoPoolConfigFlow()
    flow.hass = hass
    flow.context = {}
    result = await flow.async_step_reconfigure()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_found"


async def test_reconfigure_flow_aborts_when_entry_not_found(
    hass: HomeAssistant,
) -> None:
    """async_step_reconfigure aborts when the referenced entry was deleted."""
    flow = NeoPoolConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": "nonexistent"}
    result = await flow.async_step_reconfigure()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_found"
