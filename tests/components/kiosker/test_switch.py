"""Test the Kiosker switch platform."""

from unittest.mock import MagicMock, patch

from kiosker import (
    AuthenticationError,
    BadRequestError,
    Blackout,
    ConnectionError,
    IPAuthenticationError,
    ScreensaverState,
    TLSVerificationError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "switch.kiosker_a98be1ce_disable_screensaver"


async def _setup_switch(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    *,
    screensaver_disabled: bool = False,
) -> None:
    mock_kiosker_api.screensaver_get_state.return_value = ScreensaverState(
        visible=True, disabled=screensaver_disabled
    )
    mock_kiosker_api.blackout_get.return_value = Blackout(visible=False)
    with patch("homeassistant.components.kiosker._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    mock_kiosker_api.screensaver_get_state.return_value = ScreensaverState(
        visible=True, disabled=False
    )
    mock_kiosker_api.blackout_get.return_value = Blackout(visible=False)

    with patch("homeassistant.components.kiosker._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the screensaver disable switch on."""
    await _setup_switch(
        hass, mock_kiosker_api, mock_config_entry, screensaver_disabled=False
    )

    mock_kiosker_api.screensaver_get_state.return_value = ScreensaverState(
        visible=True, disabled=True
    )
    with patch("homeassistant.components.kiosker.switch.REFRESH_DELAY", 0):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_kiosker_api.screensaver_set_disabled_state.assert_called_once_with(True)
    assert hass.states.get(ENTITY_ID).state == "on"


async def test_turn_off(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the screensaver disable switch off."""
    await _setup_switch(
        hass, mock_kiosker_api, mock_config_entry, screensaver_disabled=True
    )

    mock_kiosker_api.screensaver_get_state.return_value = ScreensaverState(
        visible=True, disabled=False
    )
    with patch("homeassistant.components.kiosker.switch.REFRESH_DELAY", 0):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_kiosker_api.screensaver_set_disabled_state.assert_called_once_with(False)
    assert hass.states.get(ENTITY_ID).state == "off"


async def test_state_reflects_coordinator_data(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that state reflects coordinator data with no optimistic override."""
    await _setup_switch(
        hass, mock_kiosker_api, mock_config_entry, screensaver_disabled=False
    )

    # API still reports disabled=False (device hasn't updated yet)
    with patch("homeassistant.components.kiosker.switch.REFRESH_DELAY", 0):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    # Coordinator is the sole source of truth — reports off since device hasn't updated
    assert hass.states.get(ENTITY_ID).state == "off"


@pytest.mark.parametrize(
    ("exception", "expected_exception"),
    [
        (AuthenticationError, HomeAssistantError),
        (IPAuthenticationError, HomeAssistantError),
        (ConnectionError, HomeAssistantError),
        (TLSVerificationError, HomeAssistantError),
        (BadRequestError, ServiceValidationError),
    ],
)
async def test_turn_on_errors(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    expected_exception: type[Exception],
) -> None:
    """Test that API errors on turn_on are mapped to HA exceptions."""
    await _setup_switch(hass, mock_kiosker_api, mock_config_entry)

    mock_kiosker_api.screensaver_set_disabled_state.side_effect = exception("error")

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("exception", "expected_exception"),
    [
        (AuthenticationError, HomeAssistantError),
        (IPAuthenticationError, HomeAssistantError),
        (ConnectionError, HomeAssistantError),
        (TLSVerificationError, HomeAssistantError),
        (BadRequestError, ServiceValidationError),
    ],
)
async def test_turn_off_errors(
    hass: HomeAssistant,
    mock_kiosker_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: type[Exception],
    expected_exception: type[Exception],
) -> None:
    """Test that API errors on turn_off are mapped to HA exceptions."""
    await _setup_switch(
        hass, mock_kiosker_api, mock_config_entry, screensaver_disabled=True
    )

    mock_kiosker_api.screensaver_set_disabled_state.side_effect = exception("error")

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
