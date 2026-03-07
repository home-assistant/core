"""Test the Enphase Envoy services."""

from unittest.mock import AsyncMock, patch

import orjson
from pyenphase import EnvoyError
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.enphase_envoy.const import DOMAIN, Platform
from homeassistant.components.enphase_envoy.services import (
    ACTION_COORDINATORS,
    ACTION_INSPECT,
    ATTR_ENDPOINT,
    ATTR_ENVOY_DEVICE_ID,
    setup_envoy_service_actions,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
    ],
    indirect=["mock_envoy"],
)
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
    assert hass.services.has_service(DOMAIN, ACTION_INSPECT)
    assert snapshot == list(hass.services.async_services_for_domain(DOMAIN).keys())


async def test_service_load_unload(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service loading and unloading."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # test with unloaded config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    with pytest.raises(vol.Invalid, match=("required key not provided")):
        await hass.services.async_call(
            DOMAIN,
            ACTION_INSPECT,
            {},
            blocking=True,
            return_response=True,
        )

    # test with simulated second loaded envoy for COV on envoy_coordinators_list handling
    with (
        patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]),
        patch.dict(
            hass.data[DOMAIN][ACTION_COORDINATORS], {"4321": "hello world"}, clear=True
        ),
    ):
        await setup_integration(hass, config_entry)
        assert config_entry.state is ConfigEntryState.LOADED

        # existing envoy_coordinators_list entry for COV of return in service setup
        setup_envoy_service_actions(hass)

        # existing envoy_coordinators_list entry for COV of return in service unload.
        await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("user_endpoint", "normalized_endpoint"),
    [
        ("/some/endpoint", "/some/endpoint"),
        ("some/endpoint", "/some/endpoint"),
    ],
)
async def test_service_inspect_json(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    user_endpoint: str,
    normalized_endpoint: str,
) -> None:
    """Test inspect service action for json data return."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = await async_load_json_object_fixture(hass, "envoy.json", DOMAIN)
    data = data.get("data", {}).get("system_production", {"Dont": "Know"})

    mock_envoy.request.return_value.text.return_value = orjson.dumps(data).decode()

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_INSPECT,
        {ATTR_ENDPOINT: user_endpoint},
        blocking=True,
        return_response=True,
    )
    assert result["endpoint"] == normalized_endpoint
    assert result["data"] == data


async def test_service_inspect_text(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action for text data return."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = "Hello world, this is a test string."

    mock_envoy.request.return_value.text.return_value = data

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_INSPECT,
        {ATTR_ENDPOINT: "/some/endpoint"},
        blocking=True,
        return_response=True,
    )

    assert result["endpoint"] == "/some/endpoint"
    assert result["data"] == data


async def test_service_inspect_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action for html error return."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = await async_load_json_object_fixture(hass, "envoy.json", DOMAIN)
    data = data.get("data", {}).get("system_production", {"Dont": "Know"})

    mock_envoy.request.return_value.text.return_value = orjson.dumps(data).decode()
    mock_envoy.request.return_value.status = 320

    with pytest.raises(
        HomeAssistantError,
        match="Error communicating with Envoy API on",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_INSPECT,
            {ATTR_ENDPOINT: "/some/endpoint"},
            blocking=True,
            return_response=True,
        )


async def test_service_inspect_uninitialized(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action for envoy not initialized."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = await async_load_json_object_fixture(hass, "envoy.json", DOMAIN)
    data = data.get("data", {}).get("system_production", {"Dont": "Know"})

    mock_envoy.request.return_value.text.return_value = orjson.dumps(data).decode()
    mock_envoy.data = None

    with pytest.raises(
        HomeAssistantError,
        match="inspect: Enphase Envoy is not yet initialized",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_INSPECT,
            {ATTR_ENDPOINT: "/some/endpoint"},
            blocking=True,
            return_response=True,
        )


async def test_service_inspect_request_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action for request error return."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    mock_envoy.request.side_effect = EnvoyError("Test error")

    with pytest.raises(
        HomeAssistantError,
        match="Error communicating with Envoy API on",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_INSPECT,
            {ATTR_ENDPOINT: "/some/endpoint"},
            blocking=True,
            return_response=True,
        )


async def test_service_inspect_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action with optional device_id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = await async_load_json_object_fixture(hass, "envoy.json", DOMAIN)
    data = data.get("data", {}).get("system_production", {"Dont": "Know"})

    mock_envoy.request.return_value.text.return_value = orjson.dumps(data).decode()

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get(
        "sensor.envoy_1234_lifetime_energy_production"
    ).device_id

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_INSPECT,
        {ATTR_ENDPOINT: "/some/endpoint", ATTR_ENVOY_DEVICE_ID: device_id},
        blocking=True,
        return_response=True,
    )
    assert result["endpoint"] == "/some/endpoint"
    assert result["data"] == data


async def test_service_inspect_device_id_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action for wrong device_id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = await async_load_json_object_fixture(hass, "envoy.json", DOMAIN)
    data = data.get("data", {}).get("system_production", {"Dont": "Know"})

    mock_envoy.request.return_value.text.return_value = orjson.dumps(data).decode()

    device_id = "some-bogus-device-id"

    with pytest.raises(
        ServiceValidationError,
        match="No Envoy found by inspect for device_id some-bogus-device-id. Specify a correct",
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_INSPECT,
            {ATTR_ENDPOINT: "/some/endpoint", ATTR_ENVOY_DEVICE_ID: device_id},
            blocking=True,
            return_response=True,
        )


async def test_service_inspect_via_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action with child device id specified."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = await async_load_json_object_fixture(hass, "envoy.json", DOMAIN)
    data = data.get("data", {}).get("system_production", {"Dont": "Know"})

    mock_envoy.request.return_value.text.return_value = orjson.dumps(data).decode()

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get("sensor.inverter_1").device_id

    result = await hass.services.async_call(
        DOMAIN,
        ACTION_INSPECT,
        {ATTR_ENDPOINT: "/some/endpoint", ATTR_ENVOY_DEVICE_ID: device_id},
        blocking=True,
        return_response=True,
    )
    assert result["endpoint"] == "/some/endpoint"
    assert result["data"] == data


async def test_service_inspect_dual_envoy_with_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action with device_id specified and multiple envoys."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = await async_load_json_object_fixture(hass, "envoy.json", DOMAIN)
    data = data.get("data", {}).get("system_production", {"Dont": "Know"})

    mock_envoy.request.return_value.text.return_value = orjson.dumps(data).decode()

    entity_reg = er.async_get(hass)
    device_id = entity_reg.async_get("sensor.inverter_1").device_id

    # dual envoy with device_id should work and find correct coordinator
    with (
        patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]),
        patch.dict(
            hass.data[DOMAIN][ACTION_COORDINATORS],
            {"4321": "hello world"},
        ),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            ACTION_INSPECT,
            {ATTR_ENDPOINT: "/some/endpoint", ATTR_ENVOY_DEVICE_ID: device_id},
            blocking=True,
            return_response=True,
        )

        assert result["endpoint"] == "/some/endpoint"
        assert result["data"] == data


async def test_service_inspect_dual_envoy_no_device_id(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test inspect service action with no device_id specified and multiple envoys."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    data = await async_load_json_object_fixture(hass, "envoy.json", DOMAIN)
    data = data.get("data", {}).get("system_production", {"Dont": "Know"})

    mock_envoy.request.return_value.text.return_value = orjson.dumps(data).decode()

    # dual envoy with no device_id should raise
    with (
        patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]),
        patch.dict(
            hass.data[DOMAIN][ACTION_COORDINATORS],
            {"4321": "hello world"},
        ),
        pytest.raises(
            ServiceValidationError,
            match="No Envoy found by inspect. Configure an Envoy",
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            ACTION_INSPECT,
            {ATTR_ENDPOINT: "/some/endpoint"},
            blocking=True,
            return_response=True,
        )
