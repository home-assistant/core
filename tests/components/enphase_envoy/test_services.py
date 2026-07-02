"""Test the Enphase Envoy services."""

from unittest.mock import AsyncMock, patch

from pyenphase import EnvoyTokenAuth
from pyenphase.auth import EnvoyLegacyAuth
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import DOMAIN, Platform
from homeassistant.components.enphase_envoy.services import (
    ACTION_TOKEN_LIFETIME,
    ATTR_ENVOY_DEVICE_ID,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import envoy_token, setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_has_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the existence of the Enphase Envoy Services."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, ACTION_TOKEN_LIFETIME)
    assert snapshot == list(hass.services.async_services_for_domain(DOMAIN).keys())


async def test_service_load_unload(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service loading and unloading."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    # test with unloaded config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    with pytest.raises(ServiceValidationError, match=("No Envoy found")):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            {},
            blocking=True,
            return_response=True,
        )


async def test_service_token_lifetime_value(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test token_lifetime service action for data return."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_TOKEN_LIFETIME,
        blocking=True,
        return_response=True,
    )
    assert result["lifetime"] == 200


async def test_service_uninitialized(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action for envoy not initialized."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    mock_envoy.data = None

    with pytest.raises(
        HomeAssistantError,
        match="Enphase Envoy is not yet initialized",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            blocking=True,
            return_response=True,
        )


async def test_service_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action with optional device_id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get(
        "sensor.envoy_1234_lifetime_energy_production"
    ).device_id

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_TOKEN_LIFETIME,
        {ATTR_ENVOY_DEVICE_ID: device_id},
        blocking=True,
        return_response=True,
    )
    assert result["lifetime"] == 200


async def test_service_device_id_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action for wrong device_id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    device_id = "some-bogus-device-id"

    with pytest.raises(
        ServiceValidationError,
        match="No Envoy found",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            {ATTR_ENVOY_DEVICE_ID: device_id},
            blocking=True,
            return_response=True,
        )


async def test_service_via_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action with child device id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get("sensor.inverter_1").device_id

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_TOKEN_LIFETIME,
        {ATTR_ENVOY_DEVICE_ID: device_id},
        blocking=True,
        return_response=True,
    )
    assert result["lifetime"] == 200


async def test_service_dual_envoy_with_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action with device_id specified and multiple envoys."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    # Add second Envoy config entry
    token = envoy_token(300)
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e73",
        title="Envoy 2345",
        unique_id="2345",
        data={
            CONF_HOST: "127.0.0.2",
            CONF_NAME: "Envoy 2345",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: token,
        },
    )

    mock_envoy.auth = EnvoyTokenAuth("127.0.0.2", token=token, envoy_serial="2345")
    mock_envoy.serial_number = "2345"
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, second_entry)

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get(
        "sensor.envoy_2345_lifetime_energy_production"
    ).device_id

    # dual envoy with device_id should work and find correct coordinator
    result = await hass.services.async_call(
        DOMAIN,
        ACTION_TOKEN_LIFETIME,
        {ATTR_ENVOY_DEVICE_ID: device_id},
        blocking=True,
        return_response=True,
    )

    assert result["lifetime"] == 300


async def test_service_dual_envoy_no_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service action with no device_id specified and multiple envoys."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    # Add second Envoy config entry
    token = envoy_token(300)
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e73",
        title="Envoy 2345",
        unique_id="2345",
        data={
            CONF_HOST: "127.0.0.2",
            CONF_NAME: "Envoy 2345",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: token,
        },
    )
    mock_envoy.auth = EnvoyTokenAuth("127.0.0.2", token=token, envoy_serial="2345")
    mock_envoy.serial_number = "2345"
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, second_entry)

    # dual envoy and service without device_id should raise
    with (
        pytest.raises(
            ServiceValidationError,
            match="No Envoy found",
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            blocking=True,
            return_response=True,
        )


async def test_service_token_lifetime_value_with_prev7(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test token_lifetime service action for pre-V7 firmware."""
    mock_envoy.firmware = "5.1.1"
    mock_envoy.auth = EnvoyLegacyAuth(
        "127.0.0.1", username="test-username", password="test-password"
    )
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)

    with pytest.raises(
        ServiceValidationError,
        match="only used with firmware",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            blocking=True,
            return_response=True,
        )
