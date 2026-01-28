"""Test the Coolmaster config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.coolmaster.config_flow import AVAILABLE_MODES
from homeassistant.components.coolmaster.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _flow_data(advanced=False):
    options = {"host": "1.1.1.1"}
    for mode in AVAILABLE_MODES:
        options[mode] = True
    options["swing_support"] = False
    if advanced:
        options["send_wakeup_prompt"] = True
    return options


async def test_form_non_advanced(hass: HomeAssistant) -> None:
    """Test we get the form in non-advanced mode."""
    await form_base(hass, advanced=False)


async def test_form_advanced(hass: HomeAssistant) -> None:
    """Test we get the form in advanced mode."""
    await form_base(hass, advanced=True)


async def form_base(hass: HomeAssistant, advanced: bool) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_USER,
            "show_advanced_options": advanced,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
            return_value={"test_id": "test_unit"},
        ),
        patch(
            "homeassistant.components.coolmaster.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data(advanced)
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    _expected_data = {
        "host": "1.1.1.1",
        "port": 10102,
        "supported_modes": AVAILABLE_MODES,
        "swing_support": False,
        "send_wakeup_prompt": False,
    }
    if advanced:
        _expected_data["send_wakeup_prompt"] = True
    assert result2["data"] == _expected_data
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_timeout(hass: HomeAssistant) -> None:
    """Test we handle a connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
        side_effect=TimeoutError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_connection_refused(hass: HomeAssistant) -> None:
    """Test we handle a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
        side_effect=ConnectionRefusedError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_no_units(hass: HomeAssistant) -> None:
    """Test we handle no units found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
        return_value={},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "no_units"}
