"""Test the Bryant Evolution config flow."""

from unittest.mock import DEFAULT, AsyncMock, patch

from evolutionhttp import BryantEvolutionLocalClient

from homeassistant import config_entries
from homeassistant.components.bryant_evolution.const import CONF_SYSTEM_ZONE, DOMAIN
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch.object(
            BryantEvolutionLocalClient,
            "enumerate_zones",
            return_value=DEFAULT,
        ) as mock_call,
    ):
        mock_call.side_effect = lambda system_id, filename: {
            1: [1, 2],
            2: [3, 4],
        }.get(system_id, [])
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILENAME: "test_form_success",
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY, result
    assert result["title"] == "SAM at test_form_success"
    assert result["data"] == {
        CONF_FILENAME: "test_form_success",
        CONF_SYSTEM_ZONE: [(1, 1), (1, 2), (2, 3), (2, 4)],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch.object(
            BryantEvolutionLocalClient,
            "enumerate_zones",
            return_value=DEFAULT,
        ) as mock_call,
    ):
        mock_call.return_value = []
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILENAME: "test_form_cannot_connect",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with (
        patch.object(
            BryantEvolutionLocalClient,
            "enumerate_zones",
            return_value=DEFAULT,
        ) as mock_call,
    ):
        mock_call.side_effect = lambda system_id, filename: {
            1: [1, 2],
            2: [3, 4],
        }.get(system_id, [])
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILENAME: "some-serial",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SAM at some-serial"
    assert result["data"] == {
        CONF_FILENAME: "some-serial",
        CONF_SYSTEM_ZONE: [(1, 1), (1, 2), (2, 3), (2, 4)],
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect_bad_file(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error from a missing file."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            # This file does not exist.
            CONF_FILENAME: "test_form_cannot_connect_bad_file",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that reconfigure discovers additional systems and zones."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Configure initial set of systems and zones.
    with (
        patch.object(
            BryantEvolutionLocalClient,
            "enumerate_zones",
            return_value=DEFAULT,
        ) as mock_call,
    ):
        mock_call.side_effect = lambda system_id, filename: {
            1: [1, 2],
            2: [3, 4],
        }.get(system_id, [])
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILENAME: "test_reconfigure",
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY, result
    assert result["title"] == "SAM at test_reconfigure"
    assert result["data"] == {
        CONF_FILENAME: "test_reconfigure",
        CONF_SYSTEM_ZONE: [(1, 1), (1, 2), (2, 3), (2, 4)],
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Reconfigure with additional systems and zones.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": hass.config_entries.async_entries()[0].entry_id,
        },
    )
    with (
        patch.object(
            BryantEvolutionLocalClient,
            "enumerate_zones",
            return_value=DEFAULT,
        ) as mock_call,
    ):
        mock_call.side_effect = lambda system_id, filename: {
            1: [1],
            2: [3, 4, 5],
        }.get(system_id, [])
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILENAME: "test_reconfigure",
            },
        )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT, result
    assert result["reason"] == "reconfigured"
    config_entry = hass.config_entries.async_entries()[0]
    assert config_entry.data[CONF_SYSTEM_ZONE] == [
        (1, 1),
        (2, 3),
        (2, 4),
        (2, 5),
    ]
