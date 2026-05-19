"""Tests for the OpenEVSE number platform."""

from unittest.mock import MagicMock, patch

from aiohttp import ContentTypeError, ServerTimeoutError
from openevsehttp.exceptions import (
    AuthenticationError,
    ParseJSONError,
    UnsupportedFeature,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the sensor entities."""
    with patch("homeassistant.components.openevse.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test the disabled by default sensor entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.openevse_mock_config_charge_rate", ATTR_VALUE: 32.0},
        blocking=True,
    )
    mock_charger.set_current.assert_called_once_with(32.0)


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (ValueError("out of range"), ServiceValidationError),
        (AuthenticationError("bad creds"), HomeAssistantError),
        (TimeoutError("timed out"), HomeAssistantError),
        (ServerTimeoutError("timed out"), HomeAssistantError),
        (ParseJSONError("bad json"), HomeAssistantError),
        (UnsupportedFeature("old firmware"), HomeAssistantError),
        (
            ContentTypeError(MagicMock(), (), message="bad content"),
            HomeAssistantError,
        ),
    ],
)
async def test_set_value_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    raised: Exception,
    expected: type[Exception],
) -> None:
    """Test that errors from the charger are translated to HA exceptions."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_charger.set_current.side_effect = raised

    with pytest.raises(expected):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.openevse_mock_config_charge_rate",
                ATTR_VALUE: 32.0,
            },
            blocking=True,
        )
