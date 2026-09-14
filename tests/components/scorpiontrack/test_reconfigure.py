"""Test reconfiguring a ScorpionTrack share."""

from dataclasses import replace
from unittest.mock import ANY, AsyncMock, patch

from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.const import CONF_SHARE_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, get_schema_suggested_value


@pytest.mark.parametrize(
    ("share_input", "token"),
    [
        pytest.param("updated-token", "updated-token", id="changed-token"),
        pytest.param("canonical-token", "canonical-token", id="unchanged-token"),
        pytest.param(
            "https://app.scorpiontrack.com/shared/location?token=canonical-token",
            "canonical-token",
            id="share-url",
        ),
    ],
)
async def test_reconfigure_same_share(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    share_input: str,
    token: str,
) -> None:
    """Update the token and reload without replacing the share or its entities."""
    await setup_integration(hass, mock_config_entry)
    original_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, token=token, title="New share title"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_SHARE_TOKEN)
        == "canonical-token"
    )

    with patch(
        "homeassistant.components.scorpiontrack.ScorpionTrackClient",
        return_value=mock_scorpiontrack_client,
    ) as create_client:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SHARE_TOKEN: share_input}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_SHARE_TOKEN: token}
    assert mock_config_entry.unique_id == "101"
    assert mock_config_entry.title == "Family Cars"
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == original_entities
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED
    create_client.assert_called_once_with(session=ANY, token=token)
    assert mock_scorpiontrack_client.async_get_share.await_count == 3
    speed = hass.states.get("sensor.ab12_cde_speed")
    assert speed is not None
    assert float(speed.state) == pytest.approx(48.3 * 0.621371192237334)
    assert speed.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfSpeed.MILES_PER_HOUR


async def test_reconfigure_rejects_different_share(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """Keep the original configuration when the link identifies another share."""
    mock_config_entry.add_to_hass(hass)
    mock_scorpiontrack_client.async_get_share.return_value = replace(mock_share, id=202)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
        data={CONF_SHARE_TOKEN: "another-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_share"
    assert mock_config_entry.data == {CONF_SHARE_TOKEN: "canonical-token"}
    assert mock_config_entry.unique_id == "101"


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        pytest.param(ScorpionTrackConnectionError(), "cannot_connect", id="connection"),
        pytest.param(ScorpionTrackInvalidTokenError(), "invalid_token", id="invalid"),
        pytest.param(
            ScorpionTrackShareUnavailableError(), "share_unavailable", id="unavailable"
        ),
        pytest.param(Exception(), "unknown", id="unexpected"),
    ],
)
async def test_reconfigure_validation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    error: Exception,
    expected_error: str,
) -> None:
    """Keep the reconfigure form and stored data after validation fails."""
    mock_config_entry.add_to_hass(hass)
    mock_scorpiontrack_client.async_get_share.side_effect = error
    share_input = "https://app.scorpiontrack.com/shared/location?token=updated-token"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
        data={CONF_SHARE_TOKEN: share_input},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_SHARE_TOKEN)
        == share_input
    )
    assert mock_config_entry.data == {CONF_SHARE_TOKEN: "canonical-token"}


async def test_reconfigure_malformed_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reject an empty token before updating the entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
        data={CONF_SHARE_TOKEN: " "},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_token"}
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_SHARE_TOKEN)
        == " "
    )
    assert mock_config_entry.data == {CONF_SHARE_TOKEN: "canonical-token"}
