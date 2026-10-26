"""Tests for the Bosch SHC update platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import SHCInformation
from boschshcpy.exceptions import SHCException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import setup_integration

ENTITY_ID = "update.mock_title_software_update"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the update platform."""
    with patch("homeassistant.components.bosch_shc.PLATFORMS", [Platform.UPDATE]):
        yield


def _set_information(
    session: MagicMock,
    state: SHCInformation.UpdateState,
    available_version: str | None,
) -> None:
    session.information.updateState = state
    session.information.available_version = available_version


@pytest.mark.usefixtures("mock_session")
async def test_up_to_date(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Without an offered update the entity is off and refreshed on setup."""
    _set_information(mock_session, SHCInformation.UpdateState.NO_UPDATE_AVAILABLE, None)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.0"
    mock_session.information.refresh.assert_called()


@pytest.mark.parametrize(
    ("update_state", "in_progress"),
    [
        (SHCInformation.UpdateState.UPDATE_AVAILABLE, False),
        (SHCInformation.UpdateState.INSTALLING, True),
    ],
)
@pytest.mark.usefixtures("mock_session")
async def test_update_available(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    update_state: SHCInformation.UpdateState,
    in_progress: bool,
) -> None:
    """An offered version turns the entity on and installs report progress."""
    _set_information(mock_session, update_state, "2.1")
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LATEST_VERSION] == "2.1"
    assert state.attributes[ATTR_IN_PROGRESS] is in_progress


@pytest.mark.usefixtures("mock_session")
async def test_install(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Installing starts the controller software update."""
    _set_information(mock_session, SHCInformation.UpdateState.UPDATE_AVAILABLE, "2.1")
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_session.information.start_software_update.assert_called_once_with()


@pytest.mark.usefixtures("mock_session")
async def test_install_not_ready(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Installing while the controller is not ready to activate is rejected."""
    _set_information(mock_session, SHCInformation.UpdateState.UPDATE_FAILED, "2.1")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="cannot be activated"):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_session.information.start_software_update.assert_not_called()


@pytest.mark.usefixtures("mock_session")
async def test_install_failure(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failing start call is raised as a Home Assistant error."""
    _set_information(mock_session, SHCInformation.UpdateState.UPDATE_AVAILABLE, "2.1")
    mock_session.information.start_software_update.side_effect = SHCException("boom")
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError, match="Failed to start"):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
