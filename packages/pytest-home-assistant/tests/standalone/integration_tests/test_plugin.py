"""Exercise the installed package without a Home Assistant source checkout."""

from importlib import import_module
from pathlib import Path

from aiohttp import web
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import loader
from homeassistant.components.recorder import Recorder
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.setup import async_setup_component
from pytest_homeassistant import _paths
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_object_fixture,
)
from pytest_homeassistant.components.recorder.common import (
    async_wait_recording_done,
    get_schema_module_path,
)
from pytest_homeassistant.typing import ClientSessionGenerator


async def test_custom_integration(hass: HomeAssistant) -> None:
    """Discover and run a custom integration using the standard fixtures."""
    entry = MockConfigEntry(
        domain="pytest_sample",
        data=await async_load_json_object_fixture(hass, "sample.json", "pytest_sample"),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert hass.states.get("sensor.pytest_sample").state == "ready"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get("sensor.pytest_sample") is None


@pytest.mark.usefixtures("recorder_mock", "enable_custom_integrations")
async def test_enable_custom_integrations(hass: HomeAssistant) -> None:
    """Test custom integration opt-in compatibility."""
    integration = await loader.async_get_integration(hass, "pytest_sample")
    assert not integration.is_built_in


@pytest.mark.parametrize("custom_integrations_enabled", [False])
async def test_disable_custom_integrations(hass: HomeAssistant) -> None:
    """Test disabling custom integrations."""
    with pytest.raises(loader.IntegrationNotFound):
        await loader.async_get_integration(hass, "pytest_sample")


def test_fixture_loader() -> None:
    """Load a project's fixtures without Core's tests/__init__.py."""
    assert load_json_object_fixture("sample.json") == {"state": "ready"}


def test_shared_configuration(
    hass: HomeAssistant, pytestconfig: pytest.Config, request: pytest.FixtureRequest
) -> None:
    """Default configuration uses a shared path without creating a directory."""
    config_dir = pytestconfig.rootpath / "integration_tests" / "testing_config"
    assert Path(hass.config.config_dir) == config_dir
    assert not config_dir.exists()
    assert "tmp_path" not in request.fixturenames


def test_temporary_configuration(hass_tmp_config_dir: str, tmp_path: Path) -> None:
    """Tests can opt into writable configuration outside the installed package."""
    assert Path(hass_tmp_config_dir) == tmp_path
    (Path(hass_tmp_config_dir) / "configuration.yaml").write_text("default_config:\n")


def test_temporary_configuration_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Opting into a temporary directory copies a configured source."""
    config_dir = tmp_path / "source"
    config_dir.mkdir()
    (config_dir / "configuration.yaml").write_text("default_config:\n")
    monkeypatch.setattr(_paths, "CONFIG_DIR", config_dir)

    destination = Path(request.getfixturevalue("hass_tmp_config_dir"))
    assert destination == tmp_path
    assert (destination / "configuration.yaml").read_text() == "default_config:\n"


def test_registry_snapshot(
    entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Use registry fixtures and store snapshots alongside the consuming tests."""
    entity = entity_registry.async_get_or_create(
        "sensor", "pytest_sample", "sample", suggested_object_id="sample"
    )
    assert entity == snapshot


async def test_http_client(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Initialize an HTTP client using only the package's declared dependencies."""
    assert await async_setup_component(hass, "api", {})
    client = await hass_client()
    response = await client.get("/api/")
    assert response.status == 200
    assert await response.json() == {"message": "API running."}

    class LateView(HomeAssistantView):
        """A view registered after the test server starts."""

        requires_auth = False
        url = "/api/pytest_sample"
        name = "api:pytest_sample"

        async def get(self, request: web.Request) -> web.Response:
            """Return a test response."""
            return self.json({"state": "ready"})

    hass.http.register_view(LateView())
    response = await client.get("/api/pytest_sample")
    assert response.status == 200
    assert await response.json() == {"state": "ready"}


async def test_recorder(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Run recorder fixtures with only declared package dependencies."""
    hass.states.async_set("sensor.pytest_sample", "ready")
    await async_wait_recording_done(hass)
    assert recorder_mock.is_alive()


@pytest.mark.parametrize(
    "schema",
    [
        "0",
        "9",
        "16",
        "18",
        "22",
        "23",
        "23_with_newer_columns",
        "25",
        "28",
        "30",
        "32",
        "43",
        "48",
        "50",
        "51",
    ],
)
def test_historical_recorder_schema(schema: str) -> None:
    """Historical schema helpers must not import Core's test tree."""
    module = import_module(get_schema_module_path(schema))
    assert module.Base.metadata.tables


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
def test_entity_registry_enabled_by_default() -> None:
    """Registry fixtures enable entities that are disabled by default."""
    entity = Entity()
    entity._attr_entity_registry_enabled_default = False
    assert entity.entity_registry_enabled_default
