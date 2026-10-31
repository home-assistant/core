"""Tests for Synology DSM buttons."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from synology_dsm.exceptions import SynologyDSMAPIErrorException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.synology_dsm.button import BUTTONS
from homeassistant.components.synology_dsm.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import LOCALE_EN, async_get_translations

from .common import mock_dsm_hardware, mock_dsm_information
from .consts import HOST, MACS, PASSWORD, PORT, SERIAL, USE_SSL, USERNAME


@pytest.fixture
def mock_dsm() -> Generator[MagicMock]:
    """Mock Synology DSM API calls."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)
        dsm.system = Mock(reboot=AsyncMock(), shutdown=AsyncMock())
        dsm.network = Mock(
            update=AsyncMock(return_value=True), macs=MACS, hostname=HOST
        )
        dsm.hardware = mock_dsm_hardware()
        dsm.information = mock_dsm_information()
        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.file = Mock(get_shared_folders=AsyncMock(return_value=None))
        yield dsm


@pytest.fixture
async def setup_button_platform(
    hass: HomeAssistant, mock_dsm: MagicMock
) -> MockConfigEntry:
    """Set up the Synology DSM button platform."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=mock_dsm,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", [Platform.BUTTON]),
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


async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_dsm: MagicMock,
    setup_button_platform: MockConfigEntry,
) -> None:
    """Test Synology DSM button entities."""
    await snapshot_platform(
        hass, entity_registry, snapshot, setup_button_platform.entry_id
    )


async def test_button_exception_translation(hass: HomeAssistant) -> None:
    """Test every button has a translated API error message."""
    translations = await async_get_translations(hass, LOCALE_EN, "exceptions", [DOMAIN])

    for button in BUTTONS:
        translation_key = f"component.{DOMAIN}.exceptions.{button.key}_failed.message"
        assert translations.get(translation_key) is not None


@pytest.mark.parametrize(
    ("button_key", "api_method"),
    [("reboot", "reboot"), ("shutdown", "shutdown")],
)
async def test_press_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_dsm: MagicMock,
    setup_button_platform: MockConfigEntry,
    button_key: str,
    api_method: str,
) -> None:
    """Test pressing each button calls the matching DSM API method."""
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{SERIAL}_{button_key}"
    )
    assert entity_id is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    getattr(mock_dsm.system, api_method).assert_awaited_once()


@pytest.mark.parametrize(
    ("button_key", "api_method"),
    [("reboot", "reboot"), ("shutdown", "shutdown")],
)
async def test_press_button_api_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_dsm: MagicMock,
    setup_button_platform: MockConfigEntry,
    button_key: str,
    api_method: str,
) -> None:
    """Test DSM API errors are converted to Home Assistant errors."""
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{SERIAL}_{button_key}"
    )
    assert entity_id is not None
    getattr(mock_dsm.system, api_method).side_effect = SynologyDSMAPIErrorException(
        "API", 1, {}
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert err.value.translation_key == f"{button_key}_failed"
