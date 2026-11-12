"""Tests for Synology DSM update entities."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.typing import WebSocketGenerator
from synology_dsm.api.core.package import SynoCorePackage, SynoPackage
from synology_dsm.exceptions import SynologyDSMAPINoDataException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.synology_dsm.const import DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import mock_dsm_hardware, mock_dsm_information
from .consts import HOST, MACS, PASSWORD, PORT, SERIAL, USE_SSL, USERNAME

PACKAGE_APIS = {SynoCorePackage.API_KEY: {}, SynoCorePackage.SERVER_API_KEY: {}}
AUDIO_STATION_ENTITY_ID = "update.nas_meontheinternet_com_audio_station_update"
NODE_ENTITY_ID = "update.nas_meontheinternet_com_node_js_v22_update"
PHP_ENTITY_ID = "update.nas_meontheinternet_com_php_8_4_update"


def mock_package(
    package_id: str,
    name: str,
    version: str,
    available_version: str | None,
    install_type: str = "",
) -> SynoPackage:
    """Mock an installed package and the version available for it."""
    return SynoPackage(
        {
            "additional": {"install_type": install_type},
            "id": package_id,
            "name": name,
            "version": version,
        },
        None
        if available_version is None
        else {
            "changelog": "<p>Fixed issues.</p>",
            "id": package_id,
            "version": available_version,
        },
    )


@pytest.fixture
def mock_packages() -> dict[str, SynoPackage]:
    """Mock the installed packages."""
    packages = [
        mock_package("AudioStation", "Audio Station", "7.2.1-6006", "7.2.1-6006"),
        mock_package("DhcpServer", "DHCP Server", "1.0.3-0052", "1.0.4-0054", "system"),
        mock_package("MariaDB10", "MariaDB 10", "10.11.11-1551", None),
        mock_package("Node.js_v22", "Node.js v22", "22.22.3-1010", "22.23.4-1011"),
        mock_package(
            "HiddenPackage", "Hidden package", "1.0-0001", "2.0-0001", "system_hidden"
        ),
    ]
    return {package.package_id: package for package in packages}


@pytest.fixture
def mock_dsm(mock_packages: dict[str, SynoPackage]) -> Generator[MagicMock]:
    """Mock a successful service with packages."""
    with patch("homeassistant.components.synology_dsm.common.SynologyDSM") as dsm:
        dsm.apis = PACKAGE_APIS
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)
        dsm.upgrade = Mock(
            available_version=None,
            available_version_details=None,
            update=AsyncMock(return_value=True),
            update_available=False,
        )
        dsm.package = Mock(
            update=AsyncMock(return_value=None),
            get_all_packages=lambda: list(mock_packages.values()),
            get_package=mock_packages.get,
        )
        dsm.network = Mock(
            update=AsyncMock(return_value=True), macs=MACS, hostname=HOST
        )
        dsm.hardware = mock_dsm_hardware()
        dsm.information = mock_dsm_information()
        dsm.file = Mock(get_shared_folders=AsyncMock(return_value=None))
        dsm.logout = AsyncMock(return_value=True)
        yield dsm


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Synology DSM config entry."""
    return MockConfigEntry(
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


async def setup_integration(
    hass: HomeAssistant, mock_dsm: MagicMock, entry: MockConfigEntry
) -> None:
    """Set up the Synology DSM update platform."""
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=mock_dsm,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", [Platform.UPDATE]),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_update_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_dsm: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the DSM and package update entities."""
    await setup_integration(hass, mock_dsm, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_package_installed_and_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_dsm: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_packages: dict[str, SynoPackage],
) -> None:
    """Test entities follow the packages installed after setup."""
    await setup_integration(hass, mock_dsm, mock_config_entry)
    assert hass.states.get(AUDIO_STATION_ENTITY_ID).state != STATE_UNAVAILABLE
    assert hass.states.get(PHP_ENTITY_ID) is None

    del mock_packages["AudioStation"]
    mock_packages["PHP8.4"] = mock_package(
        "PHP8.4", "PHP 8.4", "8.4.27-0051", "8.4.28-0052"
    )
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(AUDIO_STATION_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(PHP_ENTITY_ID).state == STATE_ON


async def test_package_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_dsm: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test package entities are unavailable when the update fails."""
    await setup_integration(hass, mock_dsm, mock_config_entry)

    mock_dsm.update.side_effect = SynologyDSMAPINoDataException(SynoCorePackage.API_KEY)
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(AUDIO_STATION_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("apis", "update_side_effect"),
    [
        pytest.param({SynoCorePackage.API_KEY: {}}, None, id="no_catalogue_api"),
        pytest.param(
            PACKAGE_APIS,
            SynologyDSMAPINoDataException(SynoCorePackage.API_KEY),
            id="setup_fetch_failed",
        ),
    ],
)
async def test_no_package_entities(
    hass: HomeAssistant,
    mock_dsm: MagicMock,
    mock_config_entry: MockConfigEntry,
    apis: dict[str, dict],
    update_side_effect: Exception | None,
) -> None:
    """Test no package entities are created when packages can't be fetched."""
    mock_dsm.apis = apis
    mock_dsm.package.update.side_effect = update_side_effect

    await setup_integration(hass, mock_dsm, mock_config_entry)

    assert hass.states.async_entity_ids(UPDATE_DOMAIN) == [
        "update.nas_meontheinternet_com_dsm_update"
    ]


async def test_all_package_entities_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_dsm: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_packages: dict[str, SynoPackage],
) -> None:
    """Test packages are no longer fetched when all their entities are disabled."""
    mock_config_entry.add_to_hass(hass)
    for package_id in mock_packages:
        entity_registry.async_get_or_create(
            UPDATE_DOMAIN,
            DOMAIN,
            f"{SERIAL}_{SynoCorePackage.API_KEY}:package_update_{package_id}",
            config_entry=mock_config_entry,
            disabled_by=er.RegistryEntryDisabler.USER,
        )
    await setup_integration(hass, mock_dsm, mock_config_entry)

    mock_packages["PHP8.4"] = mock_package(
        "PHP8.4", "PHP 8.4", "8.4.27-0051", "8.4.28-0052"
    )
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_dsm.reset.assert_any_call(mock_dsm.package)
    assert hass.states.async_entity_ids(UPDATE_DOMAIN) == [
        "update.nas_meontheinternet_com_dsm_update"
    ]


async def test_package_release_notes(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_dsm: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the release notes are the changelog of the available version."""
    await setup_integration(hass, mock_dsm, mock_config_entry)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "update/release_notes", "entity_id": NODE_ENTITY_ID}
    )
    result = await client.receive_json()
    assert result["result"] == "<p>Fixed issues.</p>"


async def test_first_visible_package_installed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_dsm: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_packages: dict[str, SynoPackage],
) -> None:
    """Test packages are still fetched while only hidden packages are installed."""
    for package_id in ("AudioStation", "DhcpServer", "MariaDB10", "Node.js_v22"):
        del mock_packages[package_id]
    await setup_integration(hass, mock_dsm, mock_config_entry)

    async def install_package(*args: bool) -> None:
        """Install a package, as seen by the next fetch."""
        mock_packages["PHP8.4"] = mock_package(
            "PHP8.4", "PHP 8.4", "8.4.27-0051", "8.4.28-0052"
        )

    mock_dsm.update.side_effect = install_package
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(PHP_ENTITY_ID).state == STATE_ON
