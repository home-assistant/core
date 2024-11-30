"""Test config flow."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from aiohasupervisor.models import Discovery
from aiohttp.test_utils import TestClient
import pytest

from homeassistant import config_entries
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="mock_mqtt")
def mock_mqtt_fixture(
    hass: HomeAssistant,
) -> Generator[type[config_entries.ConfigFlow]]:
    """Mock the MQTT integration's config flow."""
    mock_integration(hass, MockModule(MQTT_DOMAIN))
    mock_platform(hass, f"{MQTT_DOMAIN}.config_flow", None)

    class MqttFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async_step_hassio = AsyncMock(return_value={"type": "abort"})

    with mock_config_flow(MQTT_DOMAIN, MqttFlow):
        yield MqttFlow


@pytest.mark.usefixtures("hassio_client")
async def test_hassio_discovery_startup(
    hass: HomeAssistant,
    mock_mqtt: type[config_entries.ConfigFlow],
    addon_installed: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test startup and discovery after event."""
    get_addon_discovery_info.return_value = [
        Discovery(
            addon="mosquitto",
            service="mqtt",
            uuid=(uuid := uuid4()),
            config={
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
            },
        )
    ]
    addon_installed.return_value.name = "Mosquitto Test"

    assert get_addon_discovery_info.call_count == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert get_addon_discovery_info.call_count == 1
    assert mock_mqtt.async_step_hassio.called
    mock_mqtt.async_step_hassio.assert_called_with(
        HassioServiceInfo(
            config={
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
                "addon": "Mosquitto Test",
            },
            name="Mosquitto Test",
            slug="mosquitto",
            uuid=uuid.hex,
        )
    )


@pytest.mark.usefixtures("hassio_client")
async def test_hassio_discovery_startup_done(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_mqtt: type[config_entries.ConfigFlow],
    addon_installed: AsyncMock,
    get_addon_discovery_info: AsyncMock,
) -> None:
    """Test startup and discovery with hass discovery."""
    aioclient_mock.post(
        "http://127.0.0.1/supervisor/options",
        json={"result": "ok", "data": {}},
    )
    get_addon_discovery_info.return_value = [
        Discovery(
            addon="mosquitto",
            service="mqtt",
            uuid=(uuid := uuid4()),
            config={
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
            },
        )
    ]
    addon_installed.return_value.name = "Mosquitto Test"

    with (
        patch(
            "homeassistant.components.hassio.HassIO.update_hass_api",
            return_value={"result": "ok"},
        ),
        patch(
            "homeassistant.components.hassio.HassIO.get_info",
            Mock(side_effect=HassioAPIError()),
        ),
    ):
        await hass.async_start()
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

        assert get_addon_discovery_info.call_count == 1
        assert mock_mqtt.async_step_hassio.called
        mock_mqtt.async_step_hassio.assert_called_with(
            HassioServiceInfo(
                config={
                    "broker": "mock-broker",
                    "port": 1883,
                    "username": "mock-user",
                    "password": "mock-pass",
                    "protocol": "3.1.1",
                    "addon": "Mosquitto Test",
                },
                name="Mosquitto Test",
                slug="mosquitto",
                uuid=uuid.hex,
            )
        )


async def test_hassio_discovery_webhook(
    hass: HomeAssistant,
    hassio_client: TestClient,
    mock_mqtt: type[config_entries.ConfigFlow],
    addon_installed: AsyncMock,
    get_discovery_message: AsyncMock,
) -> None:
    """Test discovery webhook."""
    get_discovery_message.return_value = Discovery(
        addon="mosquitto",
        service="mqtt",
        uuid=(uuid := uuid4()),
        config={
            "broker": "mock-broker",
            "port": 1883,
            "username": "mock-user",
            "password": "mock-pass",
            "protocol": "3.1.1",
        },
    )
    addon_installed.return_value.name = "Mosquitto Test"

    resp = await hassio_client.post(
        f"/api/hassio_push/discovery/{uuid!s}",
        json={"addon": "mosquitto", "service": "mqtt", "uuid": str(uuid)},
    )
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    assert get_discovery_message.call_count == 1
    assert mock_mqtt.async_step_hassio.called
    mock_mqtt.async_step_hassio.assert_called_with(
        HassioServiceInfo(
            config={
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
                "addon": "Mosquitto Test",
            },
            name="Mosquitto Test",
            slug="mosquitto",
            uuid=uuid.hex,
        )
    )


TEST_UUID = str(uuid4())


@pytest.mark.parametrize(
    (
        "entry_domain",
        "entry_discovery_keys",
    ),
    [
        # Matching discovery key
        (
            "mock-domain",
            {"hassio": (DiscoveryKey(domain="hassio", key=TEST_UUID, version=1),)},
        ),
        # Matching discovery key
        (
            "mock-domain",
            {
                "hassio": (DiscoveryKey(domain="hassio", key=TEST_UUID, version=1),),
                "other": (DiscoveryKey(domain="other", key="blah", version=1),),
            },
        ),
        # Matching discovery key, other domain
        # Note: Rediscovery is not currently restricted to the domain of the removed
        # entry. Such a check can be added if needed.
        (
            "comp",
            {"hassio": (DiscoveryKey(domain="hassio", key=TEST_UUID, version=1),)},
        ),
    ],
)
@pytest.mark.parametrize(
    "entry_source",
    [
        config_entries.SOURCE_HASSIO,
        config_entries.SOURCE_IGNORE,
        config_entries.SOURCE_USER,
    ],
)
async def test_hassio_rediscover(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hassio_client: TestClient,
    addon_installed: AsyncMock,
    entry_domain: str,
    entry_discovery_keys: dict[str, tuple[DiscoveryKey, ...]],
    entry_source: str,
    get_addon_discovery_info: AsyncMock,
    get_discovery_message: AsyncMock,
) -> None:
    """Test we reinitiate flows when an ignored config entry is removed."""

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=entry_domain,
        discovery_keys=entry_discovery_keys,
        unique_id="mock-unique-id",
        state=config_entries.ConfigEntryState.LOADED,
        source=entry_source,
    )
    entry.add_to_hass(hass)

    get_discovery_message.return_value = Discovery(
        addon="mosquitto",
        service="mqtt",
        uuid=(uuid := uuid4()),
        config={
            "broker": "mock-broker",
            "port": 1883,
            "username": "mock-user",
            "password": "mock-pass",
            "protocol": "3.1.1",
        },
    )

    expected_context = {
        "discovery_key": DiscoveryKey(domain="hassio", key=uuid.hex, version=1),
        "source": config_entries.SOURCE_HASSIO,
    }

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_init.mock_calls) == 1
        assert mock_init.mock_calls[0][1][0] == "mqtt"
        assert mock_init.mock_calls[0][2]["context"] == expected_context


@pytest.mark.usefixtures("mock_async_zeroconf")
@pytest.mark.parametrize(
    (
        "entry_domain",
        "entry_discovery_keys",
        "entry_source",
        "entry_unique_id",
    ),
    [
        # Discovery key from other domain
        (
            "mock-domain",
            {"bluetooth": (DiscoveryKey(domain="bluetooth", key="test", version=1),)},
            config_entries.SOURCE_IGNORE,
            "mock-unique-id",
        ),
        # Discovery key from the future
        (
            "mock-domain",
            {"hassio": (DiscoveryKey(domain="hassio", key="test", version=2),)},
            config_entries.SOURCE_IGNORE,
            "mock-unique-id",
        ),
    ],
)
async def test_hassio_rediscover_no_match(
    hass: HomeAssistant,
    hassio_client: TestClient,
    entry_domain: str,
    entry_discovery_keys: dict[str, tuple[DiscoveryKey, ...]],
    entry_source: str,
    entry_unique_id: str,
) -> None:
    """Test we don't reinitiate flows when a non matching config entry is removed."""

    mock_integration(hass, MockModule(entry_domain))

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=entry_domain,
        discovery_keys=entry_discovery_keys,
        unique_id=entry_unique_id,
        state=config_entries.ConfigEntryState.LOADED,
        source=entry_source,
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_init.mock_calls) == 0
