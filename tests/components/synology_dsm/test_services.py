"""Tests for Synology DSM actions."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.synology_dsm.const import (
    CONF_SERIAL,
    DOMAIN,
    SERVICE_REBOOT,
    SERVICE_SHUTDOWN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized, UnknownUser

from .common import mock_dsm_hardware, mock_dsm_information
from .consts import HOST, MACS, PASSWORD, PORT, SERIAL, USE_SSL, USERNAME

from tests.common import MockConfigEntry, MockUser


@pytest.fixture
def mock_dsm() -> MagicMock:
    """Mock a successful service."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)
        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.network = Mock(
            update=AsyncMock(return_value=True), macs=MACS, hostname=HOST
        )
        dsm.hardware = mock_dsm_hardware()
        dsm.information = mock_dsm_information()
        dsm.file = Mock(get_shared_folders=AsyncMock(return_value=None))
        dsm.logout = AsyncMock(return_value=True)
        dsm.system = Mock(
            reboot=AsyncMock(return_value=True),
            shutdown=AsyncMock(return_value=True),
        )
        yield dsm


@pytest.fixture
async def setup_dsm(hass: HomeAssistant, mock_dsm: MagicMock) -> MockConfigEntry:
    """Set up a Synology DSM config entry."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=mock_dsm,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", []),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id=SERIAL,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


@pytest.mark.parametrize("service", [SERVICE_REBOOT, SERVICE_SHUTDOWN])
@pytest.mark.usefixtures("setup_dsm")
async def test_service_without_user_context(
    hass: HomeAssistant,
    mock_dsm: MagicMock,
    service: str,
) -> None:
    """Test an action called without a user, as an automation does."""
    await hass.services.async_call(DOMAIN, service, {}, blocking=True)

    assert getattr(mock_dsm.system, service).call_count == 1


@pytest.mark.parametrize("service", [SERVICE_REBOOT, SERVICE_SHUTDOWN])
@pytest.mark.usefixtures("setup_dsm")
async def test_service_as_admin(
    hass: HomeAssistant,
    mock_dsm: MagicMock,
    hass_admin_user: MockUser,
    service: str,
) -> None:
    """Test an admin user can call the action."""
    await hass.services.async_call(
        DOMAIN,
        service,
        {},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert getattr(mock_dsm.system, service).call_count == 1


@pytest.mark.parametrize("service", [SERVICE_REBOOT, SERVICE_SHUTDOWN])
@pytest.mark.usefixtures("setup_dsm")
async def test_service_as_non_admin(
    hass: HomeAssistant,
    mock_dsm: MagicMock,
    hass_read_only_user: MockUser,
    service: str,
) -> None:
    """Test a non-admin user cannot call the action."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            service,
            {},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert getattr(mock_dsm.system, service).call_count == 0


@pytest.mark.parametrize("service", [SERVICE_REBOOT, SERVICE_SHUTDOWN])
@pytest.mark.usefixtures("setup_dsm")
async def test_service_as_unknown_user(
    hass: HomeAssistant,
    mock_dsm: MagicMock,
    service: str,
) -> None:
    """Test a user that no longer exists cannot call the action."""
    with pytest.raises(UnknownUser):
        await hass.services.async_call(
            DOMAIN,
            service,
            {},
            blocking=True,
            context=Context(user_id="i-am-not-a-user"),
        )

    assert getattr(mock_dsm.system, service).call_count == 0


@pytest.mark.parametrize("service", [SERVICE_REBOOT, SERVICE_SHUTDOWN])
@pytest.mark.usefixtures("setup_dsm")
async def test_service_with_serial(
    hass: HomeAssistant,
    mock_dsm: MagicMock,
    hass_admin_user: MockUser,
    service: str,
) -> None:
    """Test the serial in the call data still resolves the device."""
    await hass.services.async_call(
        DOMAIN,
        service,
        {CONF_SERIAL: SERIAL},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert getattr(mock_dsm.system, service).call_count == 1
