"""Test the Tonewinner config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.tonewinner.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _mock_receiver(model: str | None = "AT-500") -> MagicMock:
    """Return a mock receiver that answers info queries."""
    mock_receiver = MagicMock()
    mock_receiver.connect = AsyncMock()
    mock_receiver.disconnect = AsyncMock()
    mock_receiver.query_info = AsyncMock(return_value=MagicMock(model=model))
    return mock_receiver


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form, probe the receiver and can successfully set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    mock_receiver = _mock_receiver()

    with patch(
        "homeassistant.components.tonewinner.config_flow.TonewinnerReceiver",
        return_value=mock_receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AT-500"
    assert result["data"] == {
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_MODEL: "AT-500",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    mock_receiver.connect.assert_awaited_once()
    mock_receiver.query_info.assert_awaited_once()
    mock_receiver.disconnect.assert_awaited_once()


async def test_form_unknown_model(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setup falls back to a generic title when the model is unknown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tonewinner.config_flow.TonewinnerReceiver",
        return_value=_mock_receiver(model=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tonewinner"
    assert result["data"] == {CONF_SERIAL_PORT: "/dev/ttyUSB0"}


async def test_form_duplicate_serial_port(hass: HomeAssistant) -> None:
    """Test that configuring an already configured serial port aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0", CONF_MODEL: "AT-500"},
        entry_id="existing_entry_id",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tonewinner.config_flow.TonewinnerReceiver",
        return_value=_mock_receiver(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_receiver = MagicMock()
    mock_receiver.connect = AsyncMock(side_effect=OSError("Permission denied"))
    mock_receiver.disconnect = AsyncMock()

    with patch(
        "homeassistant.components.tonewinner.config_flow.TonewinnerReceiver",
        return_value=mock_receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Test recovery from error
    with patch(
        "homeassistant.components.tonewinner.config_flow.TonewinnerReceiver",
        return_value=_mock_receiver(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test reconfiguring to a port reporting a different model updates data and title."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0", CONF_MODEL: "AT-500"},
        entry_id="test_entry_id",
        title="AT-500",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = _mock_receiver(model=None)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.tonewinner.config_flow.TonewinnerReceiver",
        return_value=_mock_receiver(model="AT-300"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_PORT: "/dev/ttyUSB1"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB1"
    assert mock_config_entry.data[CONF_MODEL] == "AT-300"
    assert mock_config_entry.title == "AT-300"


async def test_reconfigure_port_used_by_other_entry(hass: HomeAssistant) -> None:
    """Test reconfiguring onto a port owned by another entry aborts."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB1", CONF_MODEL: "AT-500"},
        entry_id="other_entry_id",
    )
    other_entry.add_to_hass(hass)
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0", CONF_MODEL: "AT-500"},
        entry_id="test_entry_id",
        title="AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.tonewinner.config_flow.TonewinnerReceiver",
        return_value=_mock_receiver(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_PORT: "/dev/ttyUSB1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfigure shows an error when the port cannot be reached."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0", CONF_MODEL: "AT-500"},
        entry_id="test_entry_id",
        title="AT-500",
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    mock_receiver = MagicMock()
    mock_receiver.connect = AsyncMock(side_effect=OSError("Permission denied"))
    mock_receiver.disconnect = AsyncMock()

    with patch(
        "homeassistant.components.tonewinner.config_flow.TonewinnerReceiver",
        return_value=mock_receiver,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_PORT: "/dev/ttyUSB1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}
