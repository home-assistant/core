"""The tests for the analytics ."""

from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from awesomeversion import AwesomeVersion
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

from homeassistant.components.analytics.analytics import (
    Analytics,
    AnalyticsInput,
    AnalyticsModifications,
    DeviceAnalyticsModifications,
    EntityAnalyticsModifications,
    async_devices_payload,
)
from homeassistant.components.analytics.const import (
    ANALYTICS_ENDPOINT_URL,
    ANALYTICS_ENDPOINT_URL_DEV,
    ATTR_BASE,
    ATTR_DIAGNOSTICS,
    ATTR_STATISTICS,
    ATTR_USAGE,
)
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import ATTR_ASSUMED_STATE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.loader import IntegrationNotFound
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration, mock_platform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

MOCK_UUID = "abcdefg"
MOCK_VERSION = "1970.1.0"
MOCK_VERSION_DEV = "1970.1.0.dev0"
MOCK_VERSION_NIGHTLY = "1970.1.0.dev19700101"


@pytest.fixture(autouse=True)
def uuid_mock() -> Generator[None]:
    """Mock the UUID."""
    with patch(
        "homeassistant.components.analytics.analytics.gen_uuid", return_value=MOCK_UUID
    ):
        yield


@pytest.fixture(autouse=True)
def ha_version_mock() -> Generator[None]:
    """Mock the core version."""
    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION",
        MOCK_VERSION,
    ):
        yield


@pytest.fixture
def installation_type_mock() -> Generator[None]:
    """Mock the async_get_system_info."""
    with patch(
        "homeassistant.components.analytics.analytics.async_get_system_info",
        return_value={"installation_type": "Home Assistant Tests"},
    ):
        yield


def _last_call_payload(aioclient: AiohttpClientMocker) -> dict[str, Any]:
    """Return the payload of the last call."""
    return aioclient.mock_calls[-1][2]


@pytest.mark.usefixtures("supervisor_client")
async def test_no_send(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test send when no preferences are defined."""
    analytics = Analytics(hass)
    with patch(
        "homeassistant.components.analytics.analytics.is_hassio",
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
            "homeassistant.components.analytics.analytics.is_hassio",
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
            "homeassistant.components.analytics.analytics.is_hassio",
            side_effect=Mock(return_value=True),
        ),
    ):
        await analytics.load()

    assert not analytics.preferences[ATTR_DIAGNOSTICS]


@pytest.mark.usefixtures("supervisor_client")
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


@pytest.mark.usefixtures("supervisor_client")
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


@pytest.mark.usefixtures("installation_type_mock", "supervisor_client")
async def test_send_base(
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

    await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


@pytest.mark.usefixtures("supervisor_client")
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
            "homeassistant.components.analytics.analytics.is_hassio",
            side_effect=Mock(return_value=True),
        ) as is_hassio_mock,
        patch(
            "homeassistant.helpers.system_info.is_hassio",
            new=is_hassio_mock,
        ),
    ):
        await analytics.load()

        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


@pytest.mark.usefixtures("installation_type_mock", "supervisor_client")
async def test_send_usage(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures("mock_hass_config")
async def test_send_usage_with_supervisor(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    supervisor_client: AsyncMock,
) -> None:
    """Test send usage with supervisor preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    hass.http = Mock(ssl_certificate=None)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_USAGE]
    hass.config.components.add("default_config")

    supervisor_client.addons.addon_info.return_value = Mock(
        slug="test_addon", protected=True, version="1", auto_update=False
    )
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
            "homeassistant.components.analytics.analytics.is_hassio",
            side_effect=Mock(return_value=True),
        ) as is_hassio_mock,
        patch(
            "homeassistant.helpers.system_info.is_hassio",
            new=is_hassio_mock,
        ),
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


@pytest.mark.usefixtures("installation_type_mock", "supervisor_client")
async def test_send_statistics(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures("mock_hass_config", "supervisor_client")
async def test_send_statistics_one_integration_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures(
    "installation_type_mock", "mock_hass_config", "supervisor_client"
)
async def test_send_statistics_disabled_integration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures(
    "installation_type_mock", "mock_hass_config", "supervisor_client"
)
async def test_send_statistics_ignored_integration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures("mock_hass_config", "supervisor_client")
async def test_send_statistics_async_get_integration_unknown_exception(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures("mock_hass_config")
async def test_send_statistics_with_supervisor(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    supervisor_client: AsyncMock,
) -> None:
    """Test send statistics preferences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]

    supervisor_client.addons.addon_info.return_value = Mock(
        slug="test_addon", protected=True, version="1", auto_update=False
    )
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
            "homeassistant.components.analytics.analytics.is_hassio",
            side_effect=Mock(return_value=True),
        ) as is_hassio_mock,
        patch(
            "homeassistant.helpers.system_info.is_hassio",
            new=is_hassio_mock,
        ),
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data == logged_data
    assert snapshot == submitted_data


@pytest.mark.usefixtures("supervisor_client")
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


@pytest.mark.usefixtures(
    "enable_custom_integrations", "installation_type_mock", "supervisor_client"
)
async def test_custom_integrations(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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


@pytest.mark.usefixtures("supervisor_client")
async def test_dev_url(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures("supervisor_client")
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


@pytest.mark.usefixtures("supervisor_client")
async def test_nightly_endpoint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures(
    "installation_type_mock", "mock_hass_config", "supervisor_client"
)
async def test_send_with_no_energy(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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


@pytest.mark.usefixtures(
    "recorder_mock", "installation_type_mock", "mock_hass_config", "supervisor_client"
)
async def test_send_with_no_energy_config(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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


@pytest.mark.usefixtures(
    "recorder_mock", "installation_type_mock", "mock_hass_config", "supervisor_client"
)
async def test_send_with_energy_config(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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


@pytest.mark.usefixtures(
    "installation_type_mock", "mock_hass_config", "supervisor_client"
)
async def test_send_usage_with_certificate(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures("recorder_mock", "installation_type_mock", "supervisor_client")
async def test_send_with_recorder(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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


@pytest.mark.usefixtures("supervisor_client")
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


@pytest.mark.usefixtures("mock_hass_config", "supervisor_client")
async def test_timeout_while_sending(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
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


@pytest.mark.usefixtures("installation_type_mock", "supervisor_client")
async def test_not_check_config_entries_if_yaml(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
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
        disabled_by=ConfigEntryDisabler.USER,
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


@pytest.mark.usefixtures("installation_type_mock", "supervisor_client")
async def test_submitting_legacy_integrations(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test submitting legacy integrations."""
    hass.http = Mock(ssl_certificate=None)
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)

    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_USAGE]
    hass.config.components = ["binary_sensor"]

    with (
        patch(
            "homeassistant.components.analytics.analytics.async_get_integrations",
            return_value={
                "default_config": mock_integration(
                    hass,
                    MockModule(
                        "legacy_binary_sensor",
                        async_setup=AsyncMock(return_value=True),
                        partial_manifest={"config_flow": False},
                    ),
                ),
            },
        ),
        patch(
            "homeassistant.config.async_hass_config_yaml",
            return_value={"binary_sensor": [{"platform": "legacy_binary_sensor"}]},
        ),
    ):
        await analytics.send_analytics()

    logged_data = caplog.records[-1].args
    submitted_data = _last_call_payload(aioclient_mock)

    assert submitted_data["integrations"] == ["legacy_binary_sensor"]
    assert submitted_data == logged_data
    assert snapshot == submitted_data


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_devices_payload_no_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test devices payload with no entities."""
    assert await async_setup_component(hass, "analytics", {})
    assert await async_devices_payload(hass) == {
        "version": "home-assistant:1",
        "home_assistant": MOCK_VERSION,
        "integrations": {},
    }

    mock_config_entry = MockConfigEntry(domain="hue")
    mock_config_entry.add_to_hass(hass)

    # Normal device with all fields
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "1")},
        sw_version="test-sw-version",
        hw_version="test-hw-version",
        name="test-name",
        manufacturer="test-manufacturer",
        model="test-model",
        model_id="test-model-id",
        suggested_area="Game Room",
        configuration_url="http://example.com/config",
    )

    # Service type device
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "2")},
        manufacturer="test-manufacturer",
        model_id="test-model-id",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    # Device without model_id
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "4")},
        manufacturer="test-manufacturer",
    )

    # Device without manufacturer
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "5")},
        model_id="test-model-id",
    )

    # Device with via_device reference
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "6")},
        manufacturer="test-manufacturer6",
        model_id="test-model-id6",
        via_device=("device", "1"),
    )

    # Device from custom integration
    mock_custom_config_entry = MockConfigEntry(domain="test")
    mock_custom_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_custom_config_entry.entry_id,
        identifiers={("device", "7")},
        manufacturer="test-manufacturer7",
        model_id="test-model-id7",
    )

    # Device from an integration with a service type
    mock_service_config_entry = MockConfigEntry(domain="uptime")
    mock_service_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_service_config_entry.entry_id,
        identifiers={("device", "8")},
        manufacturer="test-manufacturer8",
        model_id="test-model-id8",
    )

    client = await hass_client()
    response = await client.get("/api/analytics/devices")
    assert response.status == HTTPStatus.OK
    assert await response.json() == {
        "version": "home-assistant:1",
        "home_assistant": MOCK_VERSION,
        "integrations": {
            "hue": {
                "devices": [
                    {
                        "entities": [],
                        "entry_type": None,
                        "has_configuration_url": True,
                        "hw_version": "test-hw-version",
                        "manufacturer": "test-manufacturer",
                        "model": "test-model",
                        "model_id": "test-model-id",
                        "sw_version": "test-sw-version",
                        "via_device": None,
                    },
                    {
                        "entities": [],
                        "entry_type": "service",
                        "has_configuration_url": False,
                        "hw_version": None,
                        "manufacturer": "test-manufacturer",
                        "model": None,
                        "model_id": "test-model-id",
                        "sw_version": None,
                        "via_device": None,
                    },
                    {
                        "entities": [],
                        "entry_type": None,
                        "has_configuration_url": False,
                        "hw_version": None,
                        "manufacturer": "test-manufacturer",
                        "model": None,
                        "model_id": None,
                        "sw_version": None,
                        "via_device": None,
                    },
                    {
                        "entities": [],
                        "entry_type": None,
                        "has_configuration_url": False,
                        "hw_version": None,
                        "manufacturer": None,
                        "model": None,
                        "model_id": "test-model-id",
                        "sw_version": None,
                        "via_device": None,
                    },
                    {
                        "entities": [],
                        "entry_type": None,
                        "has_configuration_url": False,
                        "hw_version": None,
                        "manufacturer": "test-manufacturer6",
                        "model": None,
                        "model_id": "test-model-id6",
                        "sw_version": None,
                        "via_device": ["hue", 0],
                    },
                ],
                "entities": [],
            },
        },
    }


async def test_devices_payload_with_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test devices payload with entities."""
    assert await async_setup_component(hass, "analytics", {})

    mock_config_entry = MockConfigEntry(domain="hue")
    mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "1")},
        manufacturer="test-manufacturer",
        model_id="test-model-id",
    )
    device_entry_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "2")},
        manufacturer="test-manufacturer",
        model_id="test-model-id",
    )

    # First device

    # Entity with capabilities
    entity_registry.async_get_or_create(
        domain="light",
        platform="hue",
        unique_id="1",
        capabilities={"min_color_temp_kelvin": 2000, "max_color_temp_kelvin": 6535},
        device_id=device_entry.id,
        has_entity_name=True,
    )
    # Entity with category and device class
    entity_registry.async_get_or_create(
        domain="number",
        platform="hue",
        unique_id="1",
        device_id=device_entry.id,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        original_device_class=NumberDeviceClass.TEMPERATURE,
    )
    hass.states.async_set("number.hue_1", "2")
    # Entity with assumed state
    entity_registry.async_get_or_create(
        domain="light",
        platform="hue",
        unique_id="2",
        device_id=device_entry.id,
        has_entity_name=True,
    )
    hass.states.async_set("light.hue_2", "on", {ATTR_ASSUMED_STATE: True})
    # Entity from a different integration
    entity_registry.async_get_or_create(
        domain="light",
        platform="roomba",
        unique_id="1",
        device_id=device_entry.id,
        has_entity_name=True,
    )

    # Second device
    entity_registry.async_get_or_create(
        domain="light",
        platform="hue",
        unique_id="3",
        device_id=device_entry_2.id,
    )

    # Entity without device with unit of measurement and state class
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="hue",
        unique_id="1",
        capabilities={"state_class": "measurement"},
        original_device_class=SensorDeviceClass.TEMPERATURE,
        unit_of_measurement="°C",
    )

    client = await hass_client()
    response = await client.get("/api/analytics/devices")
    assert response.status == HTTPStatus.OK
    assert await response.json() == {
        "version": "home-assistant:1",
        "home_assistant": MOCK_VERSION,
        "integrations": {
            "hue": {
                "devices": [
                    {
                        "entities": [
                            {
                                "assumed_state": None,
                                "domain": "light",
                                "entity_category": None,
                                "has_entity_name": True,
                                "original_device_class": None,
                                "unit_of_measurement": None,
                            },
                            {
                                "assumed_state": False,
                                "domain": "number",
                                "entity_category": "config",
                                "has_entity_name": True,
                                "original_device_class": "temperature",
                                "unit_of_measurement": None,
                            },
                            {
                                "assumed_state": True,
                                "domain": "light",
                                "entity_category": None,
                                "has_entity_name": True,
                                "original_device_class": None,
                                "unit_of_measurement": None,
                            },
                        ],
                        "entry_type": None,
                        "has_configuration_url": False,
                        "hw_version": None,
                        "manufacturer": "test-manufacturer",
                        "model": None,
                        "model_id": "test-model-id",
                        "sw_version": None,
                        "via_device": None,
                    },
                    {
                        "entities": [
                            {
                                "assumed_state": None,
                                "domain": "light",
                                "entity_category": None,
                                "has_entity_name": False,
                                "original_device_class": None,
                                "unit_of_measurement": None,
                            },
                        ],
                        "entry_type": None,
                        "has_configuration_url": False,
                        "hw_version": None,
                        "manufacturer": "test-manufacturer",
                        "model": None,
                        "model_id": "test-model-id",
                        "sw_version": None,
                        "via_device": None,
                    },
                ],
                "entities": [
                    {
                        "assumed_state": None,
                        "domain": "sensor",
                        "entity_category": None,
                        "has_entity_name": False,
                        "original_device_class": "temperature",
                        "unit_of_measurement": "°C",
                    },
                ],
            },
            "roomba": {
                "devices": [],
                "entities": [
                    {
                        "assumed_state": None,
                        "domain": "light",
                        "entity_category": None,
                        "has_entity_name": True,
                        "original_device_class": None,
                        "unit_of_measurement": None,
                    },
                ],
            },
        },
    }


async def test_analytics_platforms(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test analytics platforms."""
    assert await async_setup_component(hass, "analytics", {})

    mock_config_entry = MockConfigEntry(domain="test")
    mock_config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "1")},
        manufacturer="test-manufacturer",
        model_id="test-model-id",
    )
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("device", "2")},
        manufacturer="test-manufacturer",
        model_id="test-model-id-2",
    )

    entity_registry.async_get_or_create(
        domain="sensor",
        platform="test",
        unique_id="1",
        capabilities={"options": ["secret1", "secret2"]},
    )
    entity_registry.async_get_or_create(
        domain="sensor",
        platform="test",
        unique_id="2",
        capabilities={"options": ["secret1", "secret2"]},
    )

    async def async_modify_analytics(
        hass: HomeAssistant,
        analytics_input: AnalyticsInput,
    ) -> AnalyticsModifications:
        first = True
        devices_configs = {}
        for device_id in analytics_input.device_ids:
            device_config = DeviceAnalyticsModifications()
            devices_configs[device_id] = device_config
            if first:
                first = False
            else:
                device_config.remove = True

        first = True
        entities_configs = {}
        for entity_id in analytics_input.entity_ids:
            entity_entry = entity_registry.async_get(entity_id)
            entity_config = EntityAnalyticsModifications()
            entities_configs[entity_id] = entity_config
            if first:
                first = False
                entity_config.capabilities = dict(entity_entry.capabilities)
                entity_config.capabilities["options"] = len(
                    entity_config.capabilities["options"]
                )
            else:
                entity_config.remove = True

        return AnalyticsModifications(
            devices=devices_configs,
            entities=entities_configs,
        )

    platform_mock = Mock(async_modify_analytics=async_modify_analytics)
    mock_platform(hass, "test.analytics", platform_mock)

    client = await hass_client()
    response = await client.get("/api/analytics/devices")
    assert response.status == HTTPStatus.OK
    assert await response.json() == {
        "version": "home-assistant:1",
        "home_assistant": MOCK_VERSION,
        "integrations": {
            "test": {
                "devices": [
                    {
                        "entities": [],
                        "entry_type": None,
                        "has_configuration_url": False,
                        "hw_version": None,
                        "manufacturer": "test-manufacturer",
                        "model": None,
                        "model_id": "test-model-id",
                        "sw_version": None,
                        "via_device": None,
                    },
                ],
                "entities": [
                    {
                        "assumed_state": None,
                        "domain": "sensor",
                        "entity_category": None,
                        "has_entity_name": False,
                        "original_device_class": None,
                        "unit_of_measurement": None,
                    },
                ],
            },
        },
    }
