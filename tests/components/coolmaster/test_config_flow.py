"""Test the Coolmaster config flow."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.climate import HVACMode
from homeassistant.components.coolmaster.config_flow import AVAILABLE_MODES
from homeassistant.components.coolmaster.const import DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _flow_data(
    send_wakeup_prompt: bool = False,
    host: str = "1.1.1.1",
    modes: list[str] | None = None,
    swing_support: bool = False,
) -> dict:
    options: dict = {"host": host}
    for mode in AVAILABLE_MODES:
        options[mode] = mode in modes if modes is not None else True
    options["swing_support"] = swing_support
    options["more_options"] = {"send_wakeup_prompt": send_wakeup_prompt}
    return options


def _suggested_values(result: ConfigFlowResult) -> dict[str, Any]:
    """Pull the values suggested to the user out of a form result."""
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


@pytest.mark.parametrize("send_wakeup_prompt", [True, False])
async def test_form(hass: HomeAssistant, send_wakeup_prompt: bool) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
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
            result["flow_id"], _flow_data(send_wakeup_prompt)
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 10102,
        "supported_modes": AVAILABLE_MODES,
        "swing_support": False,
        "send_wakeup_prompt": send_wakeup_prompt,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "return_value", "error"),
    [
        pytest.param(OSError(), None, "cannot_connect", id="cannot_connect"),
        pytest.param(None, {}, "no_units", id="no_units"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    side_effect: Exception | None,
    return_value: dict | None,
    error: str,
) -> None:
    """Test we handle errors from the bridge."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
        side_effect=side_effect,
        return_value=return_value,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_form_duplicate_host(hass: HomeAssistant) -> None:
    """Test we abort when a bridge on this host is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "port": 10102,
            "supported_modes": AVAILABLE_MODES,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _flow_data()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "new_host",
    [
        pytest.param("1.2.3.4", id="same_host"),
        pytest.param("5.6.7.8", id="changed_host"),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant, load_int: MockConfigEntry, new_host: str
) -> None:
    """Test reconfiguring an existing entry updates the supported modes."""
    result = await load_int.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # The entry stores modes as a list but the form uses a boolean per mode.
    suggested = _suggested_values(result)
    assert suggested["host"] == "1.2.3.4"
    assert suggested[HVACMode.OFF] is True
    assert suggested[HVACMode.COOL] is True
    assert suggested[HVACMode.HEAT] is True
    assert suggested[HVACMode.DRY] is False
    assert suggested[HVACMode.HEAT_COOL] is False
    assert suggested[HVACMode.FAN_ONLY] is False

    with (
        patch(
            "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
            return_value={"test_id": "test_unit"},
        ),
        patch(
            "homeassistant.components.coolmaster.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _flow_data(
                host=new_host,
                modes=[HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY],
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert load_int.data["host"] == new_host
    assert load_int.data["supported_modes"] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.DRY,
    ]
    # Untouched keys are preserved.
    assert load_int.data["port"] == 1234


@pytest.mark.parametrize(
    ("side_effect", "return_value", "error"),
    [
        pytest.param(OSError(), None, "cannot_connect", id="cannot_connect"),
        pytest.param(None, {}, "no_units", id="no_units"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    side_effect: Exception | None,
    return_value: dict | None,
    error: str,
) -> None:
    """Test reconfigure surfaces errors and recovers."""
    result = await load_int.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
        side_effect=side_effect,
        return_value=return_value,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    # The entry is left untouched by the failed attempt.
    assert load_int.data["host"] == "1.2.3.4"

    with (
        patch(
            "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
            return_value={"test_id": "test_unit"},
        ),
        patch(
            "homeassistant.components.coolmaster.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert load_int.data["host"] == "1.1.1.1"
    assert load_int.data["supported_modes"] == AVAILABLE_MODES


async def test_reconfigure_uses_stored_port(
    hass: HomeAssistant, load_int: MockConfigEntry
) -> None:
    """Test reconfigure validates against the port stored on the entry."""
    result = await load_int.start_reconfigure_flow(hass)

    with (
        patch(
            "homeassistant.components.coolmaster.config_flow.CoolMasterNet",
            autospec=True,
        ) as mock_coolmaster,
        patch(
            "homeassistant.components.coolmaster.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_coolmaster.return_value.status.return_value = {"test_id": "test_unit"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # The entry stores port 1234, which must be used over the default 10102.
    assert mock_coolmaster.call_args.args[1] == 1234
    assert load_int.data["port"] == 1234


async def test_reconfigure_duplicate_host(
    hass: HomeAssistant, load_int: MockConfigEntry
) -> None:
    """Test reconfigure aborts when another entry already uses the host."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "9.9.9.9",
            "port": 10102,
            "supported_modes": AVAILABLE_MODES,
        },
    )
    other_entry.add_to_hass(hass)

    result = await load_int.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _flow_data(host="9.9.9.9")
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert load_int.data["host"] == "1.2.3.4"


@pytest.mark.parametrize(
    ("initial", "updated"),
    [
        pytest.param(True, False, id="enabled_to_disabled"),
        pytest.param(False, True, id="disabled_to_enabled"),
    ],
)
async def test_reconfigure_toggles_swing_support(
    hass: HomeAssistant, initial: bool, updated: bool
) -> None:
    """Test the swing support flag round-trips through the reconfigure form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            "port": 10102,
            "supported_modes": AVAILABLE_MODES,
            "swing_support": initial,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert _suggested_values(result)["swing_support"] is initial

    with (
        patch(
            "homeassistant.components.coolmaster.config_flow.CoolMasterNet.status",
            return_value={"test_id": "test_unit"},
        ),
        patch(
            "homeassistant.components.coolmaster.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data(host="1.2.3.4", swing_support=updated)
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["swing_support"] is updated
