"""Test the V2C config flow."""

from unittest.mock import AsyncMock

import pytest
from pytrydan.exceptions import TrydanError
import voluptuous as vol

from homeassistant.components.v2c.const import (
    CONF_CONTRACTED_POWER_ENTITY,
    CONF_POWER_DEVIATION_ENTITY,
    CONF_PV_AVAILABLE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_v2c_client: AsyncMock
) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EVSE 1.1.1.1"
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (TrydanError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect(
    hass: HomeAssistant, side_effect: Exception, error: str, mock_v2c_client: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_v2c_client.get_data.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    mock_v2c_client.get_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EVSE 1.1.1.1"
    assert result["data"] == {CONF_HOST: "1.1.1.1"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
) -> None:
    """Test reconfiguring an existing entry updates its data."""
    # The mock client data returns ID "ABC123", so bind the entry to it
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="ABC123",
        data={CONF_HOST: "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "2.2.2.2"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "2.2.2.2"}


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (TrydanError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test the reconfigure flow recovers from connection errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="ABC123",
        data={CONF_HOST: "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_v2c_client.get_data.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "2.2.2.2"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_v2c_client.get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "2.2.2.2"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "2.2.2.2"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_another_device(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
) -> None:
    """Test reconfiguring aborts when a different device is targeted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="DIFFERENT_ID",
        data={CONF_HOST: "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "2.2.2.2"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "another_device"
    assert entry.data == {CONF_HOST: "1.1.1.1"}


@pytest.mark.usefixtures("mock_v2c_client")
async def test_options_flow_pv_disabled(hass: HomeAssistant) -> None:
    """Test the options flow finishes in one step when PV is not available."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="ABC123",
        data={CONF_HOST: "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_PV_AVAILABLE: False},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_PV_AVAILABLE: False}


@pytest.mark.usefixtures("mock_v2c_client")
async def test_options_flow_pv_enabled(hass: HomeAssistant) -> None:
    """Test the options flow moves to the pv step and stores helper entities."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="ABC123",
        data={CONF_HOST: "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_PV_AVAILABLE: True},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pv"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_POWER_DEVIATION_ENTITY: "number.power_deviation",
            CONF_CONTRACTED_POWER_ENTITY: "number.contracted_power",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_PV_AVAILABLE: True,
        CONF_POWER_DEVIATION_ENTITY: "number.power_deviation",
        CONF_CONTRACTED_POWER_ENTITY: "number.contracted_power",
    }


@pytest.mark.usefixtures("mock_v2c_client")
async def test_options_flow_pv_step_requires_entities(hass: HomeAssistant) -> None:
    """Test the pv step rejects submissions missing the helper entities."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="ABC123",
        data={CONF_HOST: "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_PV_AVAILABLE: True},
    )
    assert result["step_id"] == "pv"

    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {},
        )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_POWER_DEVIATION_ENTITY: "number.power_deviation",
            CONF_CONTRACTED_POWER_ENTITY: "number.contracted_power",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_PV_AVAILABLE: True,
        CONF_POWER_DEVIATION_ENTITY: "number.power_deviation",
        CONF_CONTRACTED_POWER_ENTITY: "number.contracted_power",
    }


@pytest.mark.usefixtures("mock_v2c_client")
async def test_options_flow_shows_existing_values(hass: HomeAssistant) -> None:
    """Test the init step defaults to the currently stored pv_available value."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="ABC123",
        data={CONF_HOST: "1.1.1.1"},
        options={
            CONF_PV_AVAILABLE: True,
            CONF_POWER_DEVIATION_ENTITY: "number.power_deviation",
            CONF_CONTRACTED_POWER_ENTITY: "number.contracted_power",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    schema = result["data_schema"]({})
    assert schema[CONF_PV_AVAILABLE] is True


@pytest.mark.usefixtures("mock_v2c_client")
async def test_options_flow_pv_step_prefilled(hass: HomeAssistant) -> None:
    """Test the pv step pre-populates helper entities from the config entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="ABC123",
        data={CONF_HOST: "1.1.1.1"},
        options={
            CONF_PV_AVAILABLE: True,
            CONF_POWER_DEVIATION_ENTITY: "number.power_deviation",
            CONF_CONTRACTED_POWER_ENTITY: "number.contracted_power",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_PV_AVAILABLE: True},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pv"

    # The previously stored helper entities are offered as suggested values.
    suggested = {
        marker.schema: marker.description["suggested_value"]
        for marker in result["data_schema"].schema
        if marker.description and "suggested_value" in marker.description
    }
    assert suggested == {
        CONF_POWER_DEVIATION_ENTITY: "number.power_deviation",
        CONF_CONTRACTED_POWER_ENTITY: "number.contracted_power",
    }


@pytest.mark.usefixtures("mock_v2c_client")
async def test_options_flow_disable_pv(hass: HomeAssistant) -> None:
    """Test turning photovoltaic off from an entry that had it enabled."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EVSE 1.1.1.1",
        unique_id="ABC123",
        data={CONF_HOST: "1.1.1.1"},
        options={
            CONF_PV_AVAILABLE: True,
            CONF_POWER_DEVIATION_ENTITY: "number.power_deviation",
            CONF_CONTRACTED_POWER_ENTITY: "number.contracted_power",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_PV_AVAILABLE: False},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_PV_AVAILABLE: False}
    assert CONF_POWER_DEVIATION_ENTITY not in entry.options
    assert CONF_CONTRACTED_POWER_ENTITY not in entry.options
