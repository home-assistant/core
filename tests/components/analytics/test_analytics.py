"""The tests for the analytics ."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import aiohttp
from awesomeversion import AwesomeVersion
import pytest
from syrupy import SnapshotAssertion
from syrupy.matchers import path_type

from homeassistant.components.analytics.analytics import Analytics
from homeassistant.components.analytics.const import (
    ANALYTICS_ENDPOINT_URL,
    ANALYTICS_ENDPOINT_URL_DEV,
    ATTR_BASE,
    ATTR_DIAGNOSTICS,
    ATTR_STATISTICS,
    ATTR_USAGE,
)
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import IntegrationNotFound
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_UUID = "abcdefg"
MOCK_VERSION = "1970.1.0"
MOCK_VERSION_DEV = "1970.1.0.dev0"
MOCK_VERSION_NIGHTLY = "1970.1.0.dev19700101"


@pytest.fixture(autouse=True)
def uuid_mock() -> Generator[Any, Any, None]:
    """Mock the UUID."""
    with patch("uuid.UUID.hex", new_callable=PropertyMock) as hex_mock:
        hex_mock.return_value = MOCK_UUID
        yield


@pytest.fixture(autouse=True)
def ha_version_mock() -> Generator[Any, Any, None]:
    """Mock the core version."""
    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION",
        MOCK_VERSION,
    ):
        yield


@pytest.fixture
def installation_type_mock() -> Generator[Any, Any, None]:
    """Mock the async_get_system_info."""
    with patch(
        "homeassistant.components.analytics.analytics.async_get_system_info",
        return_value={"installation_type": "Home Assistant Tests"},
    ):
        yield


def _last_call_payload(aioclient: AiohttpClientMocker) -> dict[str, Any]:
    """Return the payload of the last call."""
    return aioclient.mock_calls[-1][2]


async def test_no_send(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test send when no preferences are defined."""
    analytics = Analytics(hass)
    with patch(
        "homeassistant.components.hassio.is_hassio",
        side_effect=Mock(return_value=False),
    ):
        assert not analytics.preferences[ATTR_BASE]

        await analytics.send_analytics()

    assert "Nothing to submit" in caplog.text
    assert len(aioclient_mock.mock_calls) == 0


async def test_load_with_supervisor_diagnostics(hass: HomeAssistant) -> None:
    """Test loading with a supervisor that has diagnostics enabled."""
    analytics = Analytics(hass)
    assert not analytics.preferences[ATTR_DIAGNOSTICS]
    with (
        patch(
            "homeassistant.components.hassio.get_supervisor_info",
            side_effect=Mock(return_value={"diagnostics": True}),
        ),
        patch(
            "homeassistant.components.hassio.is_hassio",
            side_effect=Mock(return_value=True),
        ),
    ):
        await analytics.load()
    assert analytics.preferences[ATTR_DIAGNOSTICS]


async def test_load_with_supervisor_without_diagnostics(hass: HomeAssistant) -> None:
    """Test loading with a supervisor that has not diagnostics enabled."""
    analytics = Analytics(hass)
    analytics._data.preferences[ATTR_DIAGNOSTICS] = True

    assert analytics.preferences[ATTR_DIAGNOSTICS]

    with (
        patch(
            "homeassistant.components.hassio.get_supervisor_info",
            side_effect=Mock(return_value={"diagnostics": False}),
        ),
        patch(
            "homeassistant.components.hassio.is_hassio",
            side_effect=Mock(return_value=True),
        ),
    ):
        await analytics.load()

    assert not analytics.preferences[ATTR_DIAGNOSTICS]


async def test_failed_to_send(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test failed to send payload."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=400)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})
    assert analytics.preferences[ATTR_BASE]

    await analytics.send_analytics()
    assert (
        f"Sending analytics failed with statuscode 400 from {ANALYTICS_ENDPOINT_URL}"
        in caplog.text
    )


async def test_failed_to_send_raises(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test raises when failed to send payload."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, exc=aiohttp.ClientError())
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})
    assert analytics.preferences[ATTR_BASE]

    await analytics.send_analytics()
    assert "Error sending analytics" in caplog.text


async def test_send_base(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send base preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)

    await analytics.save_preferences({ATTR_BASE: True})
    assert analytics.preferences[ATTR_BASE]

    await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_base_with_supervisor(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test send base preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)

    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})
    assert analytics.preferences[ATTR_BASE]

    with (
        patch(
            "homeassistant.components.hassio.get_supervisor_info",
            side_effect=Mock(
                return_value={"supported": True, "healthy": True, "arch": "amd64"}
            ),
        ),
        patch(
            "homeassistant.components.hassio.get_os_info",
            side_effect=Mock(return_value={"board": "blue", "version": "123"}),
        ),
        patch(
            "homeassistant.components.hassio.get_info",
            side_effect=Mock(return_value={}),
        ),
        patch(
            "homeassistant.components.hassio.get_host_info",
            side_effect=Mock(return_value={}),
        ),
        patch(
            "homeassistant.components.hassio.is_hassio",
            side_effect=Mock(return_value=True),
        ),
    ):
        await analytics.load()

        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_usage(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send usage preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    hass.http = Mock(ssl_certificate=None)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})

    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_USAGE]
    hass.config.components.add("default_config")

    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={"default_config": {}},
    ):
        await analytics.send_analytics()

    assert (
        "Submitted analytics to Home Assistant servers. Information submitted includes"
        in caplog.text
    )

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_usage_with_supervisor(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test send usage with supervisor preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    hass.http = Mock(ssl_certificate=None)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_USAGE]
    hass.config.components.add("default_config")

    with (
        patch(
            "homeassistant.components.hassio.get_supervisor_info",
            side_effect=Mock(
                return_value={
                    "healthy": True,
                    "supported": True,
                    "arch": "amd64",
                    "addons": [{"slug": "test_addon"}],
                }
            ),
        ),
        patch(
            "homeassistant.components.hassio.get_os_info",
            side_effect=Mock(return_value={}),
        ),
        patch(
            "homeassistant.components.hassio.get_info",
            side_effect=Mock(return_value={}),
        ),
        patch(
            "homeassistant.components.hassio.get_host_info",
            side_effect=Mock(return_value={}),
        ),
        patch(
            "homeassistant.components.hassio.async_get_addon_info",
            side_effect=AsyncMock(
                return_value={
                    "slug": "test_addon",
                    "protected": True,
                    "version": "1",
                    "auto_update": False,
                }
            ),
        ),
        patch(
            "homeassistant.components.hassio.is_hassio",
            side_effect=Mock(return_value=True),
        ),
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_statistics(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send statistics preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]
    hass.config.components.add("default_config")

    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={"default_config": {}},
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_statistics_one_integration_fails(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
) -> None:
    """Test send statistics preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]
    hass.config.components = ["default_config"]

    with patch(
        "homeassistant.components.analytics.analytics.async_get_integrations",
        return_value={"any": IntegrationNotFound("any")},
    ):
        await analytics.send_analytics()

    post_call = aioclient_mock.mock_calls[0]
    assert "uuid" in post_call[2]
    assert post_call[2]["integration_count"] == 0


async def test_send_statistics_disabled_integration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send statistics with disabled integration."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]
    hass.config.components = ["default_config"]

    with patch(
        "homeassistant.components.analytics.analytics.async_get_integrations",
        return_value={
            "disabled_integration_manifest": mock_integration(
                hass,
                MockModule(
                    "disabled_integration",
                    async_setup=AsyncMock(return_value=True),
                    partial_manifest={"disabled": "system"},
                ),
            )
        },
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_statistics_ignored_integration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send statistics with ignored integration."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]

    mock_config_entry = MockConfigEntry(
        domain="ignored_integration",
        state=ConfigEntryState.LOADED,
        source="ignore",
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.analytics.analytics.async_get_integrations",
        return_value={
            "ignored_integration": mock_integration(
                hass,
                MockModule(
                    "ignored_integration",
                    async_setup=AsyncMock(return_value=True),
                    partial_manifest={"config_flow": True},
                ),
            ),
        },
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_statistics_async_get_integration_unknown_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
) -> None:
    """Test send statistics preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]
    hass.config.components = ["default_config"]

    with (
        pytest.raises(ValueError),
        patch(
            "homeassistant.components.analytics.analytics.async_get_integrations",
            return_value={"any": ValueError()},
        ),
    ):
        await analytics.send_analytics()


async def test_send_statistics_with_supervisor(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test send statistics preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]

    with (
        patch(
            "homeassistant.components.hassio.get_supervisor_info",
            side_effect=Mock(
                return_value={
                    "healthy": True,
                    "supported": True,
                    "arch": "amd64",
                    "addons": [{"slug": "test_addon"}],
                }
            ),
        ),
        patch(
            "homeassistant.components.hassio.get_os_info",
            side_effect=Mock(return_value={}),
        ),
        patch(
            "homeassistant.components.hassio.get_info",
            side_effect=Mock(return_value={}),
        ),
        patch(
            "homeassistant.components.hassio.get_host_info",
            side_effect=Mock(return_value={}),
        ),
        patch(
            "homeassistant.components.hassio.async_get_addon_info",
            side_effect=AsyncMock(
                return_value={
                    "slug": "test_addon",
                    "protected": True,
                    "version": "1",
                    "auto_update": False,
                }
            ),
        ),
        patch(
            "homeassistant.components.hassio.is_hassio",
            side_effect=Mock(return_value=True),
        ),
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_reusing_uuid(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reusing the stored UUID."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    analytics._data.uuid = "NOT_MOCK_UUID"

    await analytics.save_preferences({ATTR_BASE: True})

    # This is not actually called but that in itself prove the test
    await analytics.send_analytics()

    assert analytics.uuid == "NOT_MOCK_UUID"


async def test_custom_integrations(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test sending custom integrations."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    hass.http = Mock(ssl_certificate=None)
    assert await async_setup_component(hass, "test_package", {"test_package": {}})
    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})

    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={"test_package": {}},
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_dev_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test sending payload to dev url."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()

    payload = aioclient_mock.mock_calls[0]
    assert str(payload[1]) == ANALYTICS_ENDPOINT_URL_DEV


async def test_dev_url_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test sending payload to dev url that returns error."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=400)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()

    payload = aioclient_mock.mock_calls[0]
    assert str(payload[1]) == ANALYTICS_ENDPOINT_URL_DEV
    assert (
        "Sending analytics failed with statuscode 400 from"
        f" {ANALYTICS_ENDPOINT_URL_DEV}"
    ) in caplog.text


async def test_nightly_endpoint(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test sending payload to production url when running nightly."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_NIGHTLY
    ):
        await analytics.send_analytics()

    payload = aioclient_mock.mock_calls[0]
    assert str(payload[1]) == ANALYTICS_ENDPOINT_URL


async def test_send_with_no_energy(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
    caplog: pytest.LogCaptureFixture,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send base preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    hass.http = Mock(ssl_certificate=None)

    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})

    with (
        patch(
            "homeassistant.components.analytics.analytics.energy_is_configured",
            AsyncMock(),
        ) as energy_is_configured,
        patch(
            "homeassistant.components.analytics.analytics.get_recorder_instance",
            Mock(),
        ) as get_recorder_instance,
    ):
        energy_is_configured.return_value = False
        get_recorder_instance.return_value = Mock(database_engine=Mock())
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert "energy" not in submitted_data
    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_with_no_energy_config(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
    caplog: pytest.LogCaptureFixture,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send base preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)

    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})
    assert await async_setup_component(hass, "energy", {})

    with patch(
        "homeassistant.components.analytics.analytics.energy_is_configured", AsyncMock()
    ) as energy_is_configured:
        energy_is_configured.return_value = False
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data["energy"]["configured"] is False
    assert submitted_data == logged_data
    assert (
        snapshot(matcher=path_type({"recorder.version": (AwesomeVersion,)}))
        == submitted_data
    )


async def test_send_with_energy_config(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
    caplog: pytest.LogCaptureFixture,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send base preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)

    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})
    assert await async_setup_component(hass, "energy", {})

    with patch(
        "homeassistant.components.analytics.analytics.energy_is_configured", AsyncMock()
    ) as energy_is_configured:
        energy_is_configured.return_value = True
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data["energy"]["configured"] is True
    assert submitted_data == logged_data
    assert (
        snapshot(matcher=path_type({"recorder.version": (AwesomeVersion,)}))
        == submitted_data
    )


async def test_send_usage_with_certificate(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test send usage preferences with certificate."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    hass.http = Mock(ssl_certificate="/some/path/to/cert.pem")
    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})

    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_USAGE]

    await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data["certificate"] is True
    assert submitted_data == logged_data
    assert snapshot == submitted_data


async def test_send_with_recorder(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test recorder information."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    hass.http = Mock(ssl_certificate="/some/path/to/cert.pem")

    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})

    with patch(
        "homeassistant.config.load_yaml_config_file",
        return_value={"recorder": {}},
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data["recorder"]["engine"] == "sqlite"
    assert submitted_data == logged_data
    assert (
        snapshot(matcher=path_type({"recorder.version": (AwesomeVersion,)}))
        == submitted_data
    )


async def test_send_with_problems_loading_yaml(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test error loading YAML configuration."""
    analytics = Analytics(hass)

    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})
    with patch(
        "homeassistant.config.load_yaml_config_file",
        side_effect=HomeAssistantError("Error loading YAML file"),
    ):
        await analytics.send_analytics()

    assert "Error loading YAML file" in caplog.text
    assert len(aioclient_mock.mock_calls) == 0


async def test_timeout_while_sending(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    mock_hass_config: None,
) -> None:
    """Test timeout error while sending analytics."""
    analytics = Analytics(hass)
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, exc=TimeoutError())

    await analytics.save_preferences({ATTR_BASE: True})
    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()

    assert "Timeout sending analytics" in caplog.text


async def test_not_check_config_entries_if_yaml(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    installation_type_mock: Generator[Any, Any, None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test skip config entry check if defined in yaml."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    hass.http = Mock(ssl_certificate="/some/path/to/cert.pem")

    await analytics.save_preferences(
        {ATTR_BASE: True, ATTR_STATISTICS: True, ATTR_USAGE: True}
    )
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]
    hass.config.components = ["default_config"]

    mock_config_entry = MockConfigEntry(
        domain="ignored_integration",
        state=ConfigEntryState.LOADED,
        source="ignore",
        disabled_by="user",
    )
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.analytics.analytics.async_get_integrations",
            return_value={
                "default_config": mock_integration(
                    hass,
                    MockModule(
                        "default_config",
                        async_setup=AsyncMock(return_value=True),
                        partial_manifest={"config_flow": True},
                    ),
                ),
            },
        ),
        patch(
            "homeassistant.config.load_yaml_config_file",
            return_value={"default_config": {}},
        ),
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data["integration_count"] == 1
    assert submitted_data["integrations"] == ["default_config"]
    assert submitted_data == logged_data
    assert snapshot == submitted_data
