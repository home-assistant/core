"""Test the iNet Radio config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.inet.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST, MOCK_NAME, MOCK_UNIQUE_ID, _create_mock_radio

from tests.common import MockConfigEntry


def _mock_manager_with_radio(radio: MagicMock) -> MagicMock:
    """Create a mock RadioManager that returns the given radio on connect."""
    manager = MagicMock()
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.connect = AsyncMock(return_value=radio)
    manager.discover = AsyncMock()
    manager.radios = {radio.ip: radio}
    return manager


def _mock_manager_no_radios() -> MagicMock:
    """Create a mock RadioManager with no discovered radios."""
    manager = MagicMock()
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.discover = AsyncMock()
    manager.radios = {}
    return manager


async def test_manual_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful manual flow when no radios discovered."""
    radio = _create_mock_radio()
    manager_discover = _mock_manager_no_radios()
    manager_connect = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_discover,
    ):
        # No radios discovered -> goes straight to manual
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_connect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == {CONF_HOST: MOCK_HOST}
    assert result["result"].unique_id == MOCK_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful flow with discovered radios."""
    radio = _create_mock_radio()
    manager = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select the discovered radio
    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == {CONF_HOST: MOCK_HOST}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_flow_manual_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test discovery flow with manual entry selection."""
    radio = _create_mock_radio()
    manager = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": "manual"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert len(mock_setup_entry.mock_calls) == 1


async def test_cannot_connect(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test connection failure shows error and allows recovery."""
    manager_fail = _mock_manager_no_radios()
    manager_fail.connect = AsyncMock(side_effect=TimeoutError("No response"))

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_fail,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    # Try connecting and fail
    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_fail,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.200"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover with correct host
    radio = _create_mock_radio()
    manager_ok = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_ok,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we abort if the radio is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST},
        unique_id=MOCK_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    radio = _create_mock_radio()
    manager_discover = _mock_manager_no_radios()
    manager_connect = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_discover,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_connect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_unknown_error(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test unknown error during connection."""
    manager_discover = _mock_manager_no_radios()
    manager_fail = _mock_manager_no_radios()
    manager_fail.connect = AsyncMock(side_effect=RuntimeError("Unexpected"))

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_discover,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_fail,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover
    radio = _create_mock_radio()
    manager_ok = _mock_manager_with_radio(radio)

    with patch(
        "homeassistant.components.inet.config_flow.RadioManager",
        return_value=manager_ok,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: MOCK_HOST},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1
