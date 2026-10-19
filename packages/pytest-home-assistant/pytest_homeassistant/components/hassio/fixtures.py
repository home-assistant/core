"""Fixtures for testing Supervisor integrations."""

from collections.abc import Generator
from ipaddress import IPv4Address, IPv4Network
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohasupervisor import SupervisorClient, SupervisorNotFoundError
from aiohasupervisor.addons import AddonsClient
from aiohasupervisor.backups import BackupsClient
from aiohasupervisor.discovery import DiscoveryClient
from aiohasupervisor.homeassistant import HomeAssistantClient
from aiohasupervisor.host import HostClient
from aiohasupervisor.ingress import IngressClient
from aiohasupervisor.jobs import JobsClient
from aiohasupervisor.models import (
    AddonStage,
    AddonState,
    Discovery,
    DockerNetwork,
    GreenInfo,
    HomeAssistantInfo,
    HomeAssistantStats,
    HostInfo,
    InstalledAddon,
    JobsInfo,
    LogLevel,
    MountsInfo,
    NetworkInfo,
    OSInfo,
    Repository,
    ResolutionInfo,
    RootInfo,
    StoreAddon,
    StoreInfo,
    SupervisorInfo,
    SupervisorState,
    SupervisorStats,
    UpdateChannel,
    YellowInfo,
)
from aiohasupervisor.mounts import MountsClient
from aiohasupervisor.network import NetworkClient
from aiohasupervisor.os import OSClient
from aiohasupervisor.resolution import ResolutionClient
from aiohasupervisor.store import StoreClient
from aiohasupervisor.supervisor import SupervisorManagementClient
import pytest

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from homeassistant.components.hassio import AddonManager


@pytest.fixture(name="addon_manager")
def addon_manager_fixture(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> AddonManager:
    """Return an AddonManager instance."""
    from .common import mock_addon_manager  # noqa: PLC0415

    return mock_addon_manager(hass)


@pytest.fixture(name="discovery_info")
def discovery_info_fixture() -> list[Discovery]:
    """Return the discovery info from the supervisor."""
    return []


@pytest.fixture(name="discovery_info_side_effect")
def discovery_info_side_effect_fixture() -> Any | None:
    """Return the discovery info from the supervisor."""
    return None


@pytest.fixture(name="get_addon_discovery_info")
def get_addon_discovery_info_fixture(
    supervisor_client: AsyncMock,
    discovery_info: list[Discovery],
    discovery_info_side_effect: Any | None,
) -> AsyncMock:
    """Mock get add-on discovery info."""
    supervisor_client.discovery.list.return_value = discovery_info
    supervisor_client.discovery.list.side_effect = discovery_info_side_effect
    return supervisor_client.discovery.list


@pytest.fixture(name="get_discovery_message_side_effect")
def get_discovery_message_side_effect_fixture() -> Any | None:
    """Side effect for getting a discovery message by uuid."""
    return None


@pytest.fixture(name="get_discovery_message")
def get_discovery_message_fixture(
    supervisor_client: AsyncMock, get_discovery_message_side_effect: Any | None
) -> AsyncMock:
    """Mock getting a discovery message by uuid."""
    supervisor_client.discovery.get.side_effect = get_discovery_message_side_effect
    return supervisor_client.discovery.get


@pytest.fixture(name="addon_store_info_side_effect")
def addon_store_info_side_effect_fixture() -> Any | None:
    """Return the add-on store info side effect."""
    return None


@pytest.fixture(name="addon_store_info")
def addon_store_info_fixture(
    supervisor_client: AsyncMock,
    addon_store_info_side_effect: Any | None,
) -> AsyncMock:
    """Mock Supervisor add-on store info."""
    from .common import mock_addon_store_info  # noqa: PLC0415

    return mock_addon_store_info(supervisor_client, addon_store_info_side_effect)


@pytest.fixture(name="addon_info_side_effect")
def addon_info_side_effect_fixture() -> Any | None:
    """Return the add-on info side effect."""
    return None


@pytest.fixture(name="addon_info")
def addon_info_fixture(
    supervisor_client: AsyncMock, addon_info_side_effect: Any | None
) -> AsyncMock:
    """Mock Supervisor add-on info."""
    from .common import mock_addon_info  # noqa: PLC0415

    return mock_addon_info(supervisor_client, addon_info_side_effect)


@pytest.fixture(name="addon_not_installed")
def addon_not_installed_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on not installed."""
    from .common import mock_addon_not_installed  # noqa: PLC0415

    addon_info.side_effect = SupervisorNotFoundError
    return mock_addon_not_installed(addon_store_info, addon_info)


@pytest.fixture(name="addon_installed")
def addon_installed_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already installed but not running."""
    from .common import mock_addon_installed  # noqa: PLC0415

    return mock_addon_installed(addon_store_info, addon_info)


@pytest.fixture(name="addon_running")
def addon_running_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already running."""
    from .common import mock_addon_running  # noqa: PLC0415

    return mock_addon_running(addon_store_info, addon_info)


@pytest.fixture(name="install_addon_side_effect")
def install_addon_side_effect_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Any | None:
    """Return the install add-on side effect."""

    from .common import mock_install_addon_side_effect  # noqa: PLC0415

    return mock_install_addon_side_effect(addon_store_info, addon_info)


@pytest.fixture(name="install_addon")
def install_addon_fixture(
    supervisor_client: AsyncMock,
    install_addon_side_effect: Any | None,
) -> AsyncMock:
    """Mock install add-on."""
    supervisor_client.store.install_addon.side_effect = install_addon_side_effect
    return supervisor_client.store.install_addon


@pytest.fixture(name="start_addon_side_effect")
def start_addon_side_effect_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Any | None:
    """Return the start add-on options side effect."""
    from .common import mock_start_addon_side_effect  # noqa: PLC0415

    return mock_start_addon_side_effect(addon_store_info, addon_info)


@pytest.fixture(name="start_addon")
def start_addon_fixture(
    supervisor_client: AsyncMock, start_addon_side_effect: Any | None
) -> AsyncMock:
    """Mock start add-on."""
    supervisor_client.addons.start_addon.side_effect = start_addon_side_effect
    return supervisor_client.addons.start_addon


@pytest.fixture(name="restart_addon_side_effect")
def restart_addon_side_effect_fixture() -> Any | None:
    """Return the restart add-on options side effect."""
    return None


@pytest.fixture(name="restart_addon")
def restart_addon_fixture(
    supervisor_client: AsyncMock,
    restart_addon_side_effect: Any | None,
) -> AsyncMock:
    """Mock restart add-on."""
    supervisor_client.addons.restart_addon.side_effect = restart_addon_side_effect
    return supervisor_client.addons.restart_addon


@pytest.fixture(name="stop_addon")
def stop_addon_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock stop add-on."""
    return supervisor_client.addons.stop_addon


@pytest.fixture(name="addon_options")
def addon_options_fixture(addon_info: AsyncMock) -> dict[str, Any]:
    """Mock add-on options."""
    return addon_info.return_value.options


@pytest.fixture(name="set_addon_options_side_effect")
def set_addon_options_side_effect_fixture(
    addon_options: dict[str, Any],
) -> Any | None:
    """Return the set add-on options side effect."""
    from .common import mock_set_addon_options_side_effect  # noqa: PLC0415

    return mock_set_addon_options_side_effect(addon_options)


@pytest.fixture(name="set_addon_options")
def set_addon_options_fixture(
    supervisor_client: AsyncMock,
    set_addon_options_side_effect: Any | None,
) -> AsyncMock:
    """Mock set add-on options."""
    supervisor_client.addons.set_addon_options.side_effect = (
        set_addon_options_side_effect
    )
    return supervisor_client.addons.set_addon_options


@pytest.fixture(name="uninstall_addon")
def uninstall_addon_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock uninstall add-on."""
    return supervisor_client.addons.uninstall_addon


@pytest.fixture(name="create_backup")
def create_backup_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock create backup."""
    return supervisor_client.backups.partial_backup


@pytest.fixture(name="update_addon")
def update_addon_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock update add-on."""
    return supervisor_client.store.update_addon


@pytest.fixture(name="store_addons")
def store_addons_fixture() -> list[StoreAddon]:
    """Mock store addons list."""
    return []


@pytest.fixture(name="store_repositories")
def store_repositories_fixture() -> list[Repository]:
    """Mock store repositories list."""
    return []


@pytest.fixture(name="store_info")
def store_info_fixture(
    supervisor_client: AsyncMock,
    store_addons: list[StoreAddon],
    store_repositories: list[Repository],
) -> AsyncMock:
    """Mock store info."""
    supervisor_client.store.info.return_value = StoreInfo(
        addons=store_addons, repositories=store_repositories
    )
    return supervisor_client.store.info


@pytest.fixture(name="addon_stats")
def addon_stats_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock addon stats info."""
    from .common import mock_addon_stats  # noqa: PLC0415

    return mock_addon_stats(supervisor_client)


@pytest.fixture(name="addon_changelog")
def addon_changelog_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock addon changelog."""
    supervisor_client.store.addon_changelog.return_value = ""
    return supervisor_client.store.addon_changelog


@pytest.fixture(name="supervisor_is_connected")
def supervisor_is_connected_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock supervisor is connected."""
    supervisor_client.supervisor.ping.return_value = None
    return supervisor_client.supervisor.ping


@pytest.fixture(name="resolution_info")
def resolution_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock resolution info from supervisor."""
    supervisor_client.resolution.info.return_value = ResolutionInfo(
        suggestions=[],
        unsupported=[],
        unhealthy=[],
        issues=[],
        checks=[],
    )
    return supervisor_client.resolution.info


@pytest.fixture(name="resolution_suggestions_for_issue")
def resolution_suggestions_for_issue_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock suggestions by issue from supervisor resolution."""
    supervisor_client.resolution.suggestions_for_issue.return_value = []
    return supervisor_client.resolution.suggestions_for_issue


@pytest.fixture(name="jobs_info")
def jobs_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock jobs info from supervisor."""
    supervisor_client.jobs.info.return_value = JobsInfo(ignore_conditions=[], jobs=[])
    return supervisor_client.jobs.info


@pytest.fixture(name="os_yellow_info")
def os_yellow_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock yellow info API from supervisor OS."""
    supervisor_client.os.yellow_info.return_value = YellowInfo(
        disk_led=True, heartbeat_led=True, power_led=True
    )
    return supervisor_client.os.yellow_info


@pytest.fixture(name="os_green_info")
def os_green_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock green info API from supervisor OS."""
    supervisor_client.os.green_info.return_value = GreenInfo(
        activity_led=True, power_led=True, system_health_led=True
    )
    return supervisor_client.os.green_info


@pytest.fixture(name="supervisor_root_info")
def supervisor_root_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock root info API from supervisor."""
    supervisor_client.info.return_value = RootInfo(
        supervisor="222",
        homeassistant="0.110.0",
        hassos="1.2.3",
        docker="",
        hostname=None,
        operating_system=None,
        features=[],
        machine=None,
        machine_id=None,
        arch="",
        state=SupervisorState.RUNNING,
        supported_arch=[],
        supported=True,
        channel=UpdateChannel.STABLE,
        logging=LogLevel.INFO,
        timezone="Etc/UTC",
    )
    return supervisor_client.info


@pytest.fixture(name="host_info")
def host_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock host info API from supervisor."""
    supervisor_client.host.info.return_value = HostInfo(
        agent_version=None,
        apparmor_version=None,
        chassis="vm",
        virtualization=None,
        cpe=None,
        deployment=None,
        disk_free=1.6,
        disk_total=100.0,
        disk_used=98.4,
        disk_life_time=None,
        features=[],
        hostname=None,
        llmnr_hostname=None,
        kernel="4.19.0-6-amd64",
        operating_system="Debian GNU/Linux 10 (buster)",
        timezone=None,
        dt_utc=None,
        dt_synchronized=None,
        use_ntp=None,
        startup_time=None,
        boot_timestamp=None,
        broadcast_llmnr=None,
        broadcast_mdns=None,
    )
    return supervisor_client.host.info


@pytest.fixture(name="homeassistant_info")
def homeassistant_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock Home Assistant info API from supervisor."""
    supervisor_client.homeassistant.info.return_value = HomeAssistantInfo(
        version="1.0.0",
        version_latest="1.0.0",
        update_available=False,
        machine=None,
        ip_address=IPv4Address("172.30.32.1"),
        arch=None,
        image="homeassistant",
        boot=True,
        port=8123,
        ssl=False,
        watchdog=True,
        audio_input=None,
        audio_output=None,
        backups_exclude_database=False,
        duplicate_log_file=False,
    )
    return supervisor_client.homeassistant.info


@pytest.fixture(name="supervisor_info")
def supervisor_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock supervisor info API from supervisor."""
    supervisor_client.supervisor.info.return_value = SupervisorInfo(
        version="1.0.0",
        version_latest="1.0.0",
        update_available=False,
        channel=UpdateChannel.STABLE,
        arch="",
        supported=True,
        healthy=True,
        ip_address=IPv4Address("172.30.32.2"),
        timezone=None,
        logging=LogLevel.INFO,
        debug=False,
        debug_block=False,
        diagnostics=None,
        auto_update=True,
        country=None,
        detect_blocking_io=False,
        feature_flags={},
    )
    return supervisor_client.supervisor.info


@pytest.fixture(name="addons_list")
def addons_list_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock addons list API from supervisor."""
    supervisor_client.addons.list.return_value = [
        InstalledAddon(
            detached=False,
            advanced=False,
            available=True,
            build=False,
            description="",
            homeassistant=None,
            icon=False,
            logo=False,
            name="test",
            repository="core",
            slug="test",
            stage=AddonStage.STABLE,
            update_available=True,
            url="https://github.com/home-assistant/addons/test",
            version_latest="2.0.1",
            version="2.0.0",
            state=AddonState.STARTED,
        ),
        InstalledAddon(
            detached=False,
            advanced=False,
            available=True,
            build=False,
            description="",
            homeassistant=None,
            icon=False,
            logo=False,
            name="test2",
            repository="core",
            slug="test2",
            stage=AddonStage.STABLE,
            update_available=False,
            url="https://github.com",
            version_latest="3.1.0",
            version="3.1.0",
            state=AddonState.STOPPED,
        ),
    ]
    return supervisor_client.addons.list


@pytest.fixture(name="network_info")
def network_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock network info API from supervisor."""
    supervisor_client.network.info.return_value = NetworkInfo(
        interfaces=[],
        docker=DockerNetwork(
            interface="hassio",
            address=IPv4Network("172.30.32.0/23"),
            gateway=IPv4Address("172.30.32.1"),
            dns=IPv4Address("172.30.32.3"),
        ),
        host_internet=True,
        supervisor_internet=True,
    )
    return supervisor_client.network.info


@pytest.fixture(name="os_info")
def os_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock os info API from supervisor."""
    supervisor_client.os.info.return_value = OSInfo(
        version="1.0.0",
        version_latest="1.0.0",
        version_pending=None,
        update_available=False,
        board=None,
        boot=None,
        data_disk=None,
        boot_slots={},
    )
    return supervisor_client.os.info


@pytest.fixture(name="homeassistant_stats")
def homeassistant_stats_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock Home Assistant stats API from supervisor."""
    supervisor_client.homeassistant.stats.return_value = HomeAssistantStats(
        cpu_percent=0.99,
        memory_usage=182611968,
        memory_limit=3977146368,
        memory_percent=4.59,
        network_rx=362570232,
        network_tx=82374138,
        blk_read=46010945536,
        blk_write=15051526144,
    )
    return supervisor_client.homeassistant.stats


@pytest.fixture(name="supervisor_stats")
def supervisor_stats_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock supervisor stats API from supervisor."""
    supervisor_client.supervisor.stats.return_value = SupervisorStats(
        cpu_percent=0.99,
        memory_usage=182611968,
        memory_limit=3977146368,
        memory_percent=4.59,
        network_rx=362570232,
        network_tx=82374138,
        blk_read=46010945536,
        blk_write=15051526144,
    )
    return supervisor_client.supervisor.stats


@pytest.fixture(name="ingress_panels")
def ingress_panels_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock ingress panels API from supervisor."""
    supervisor_client.ingress.panels.return_value = {}
    return supervisor_client.ingress.panels


@pytest.fixture(name="supervisor_client")
def supervisor_client() -> Generator[AsyncMock]:
    """Mock the supervisor client."""
    supervisor_client = AsyncMock(spec=SupervisorClient)
    supervisor_client.addons = AsyncMock(spec=AddonsClient)
    supervisor_client.backups = AsyncMock(spec=BackupsClient)
    supervisor_client.discovery = AsyncMock(spec=DiscoveryClient)
    supervisor_client.homeassistant = AsyncMock(spec=HomeAssistantClient)
    supervisor_client.host = AsyncMock(spec=HostClient)
    supervisor_client.ingress = AsyncMock(spec=IngressClient)
    supervisor_client.jobs = AsyncMock(spec=JobsClient)
    supervisor_client.jobs.info.return_value = JobsInfo(ignore_conditions=[], jobs=[])
    supervisor_client.mounts = AsyncMock(spec=MountsClient)
    supervisor_client.mounts.info.return_value = MagicMock(
        spec=MountsInfo, default_backup_mount=None, mounts=[]
    )
    supervisor_client.network = AsyncMock(spec=NetworkClient)
    supervisor_client.os = AsyncMock(spec=OSClient)
    supervisor_client.resolution = AsyncMock(spec=ResolutionClient)
    supervisor_client.supervisor = AsyncMock(spec=SupervisorManagementClient)
    supervisor_client.store = AsyncMock(spec=StoreClient)

    with (
        patch(
            "homeassistant.components.hassio.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.handler.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.addon_manager.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.addon_panel.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.backup.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.discovery.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.coordinator.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.repairs.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.services.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.update_helper.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.homeassistant_hardware.util."
            "get_supervisor_client",
            return_value=supervisor_client,
        ),
    ):
        yield supervisor_client
