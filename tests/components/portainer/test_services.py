"""Test for Portainer services."""

from datetime import timedelta
from unittest.mock import AsyncMock

from pyportainer import (
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
import pytest
from voluptuous import MultipleInvalid

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.components.portainer.services import (
    ATTR_CONTAINER_DEVICE_ID,
    ATTR_DANGLING,
    ATTR_DATE_UNTIL,
    ATTR_PULL_IMAGE,
    ATTR_TIMEOUT,
    SERVICE_PRUNE_IMAGES,
    SERVICE_RECREATE_CONTAINER,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceRegistry

from . import setup_integration
from .conftest import TEST_CONTAINER_ID, TEST_CONTAINER_NAME, TEST_ENTRY

from tests.common import MockConfigEntry

TEST_ENDPOINT_ID = 1
TEST_DEVICE_IDENTIFIER = f"{TEST_ENTRY}_{TEST_ENDPOINT_ID}"

TEST_CONTAINER_DEVICE_IDENTIFIER = (
    f"{TEST_ENTRY}_{TEST_ENDPOINT_ID}_{TEST_CONTAINER_NAME}"
)


async def test_services(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests that the services are correct."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_IDENTIFIER)}
    )
    assert device is not None
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRUNE_IMAGES,
        {
            ATTR_DEVICE_ID: device.id,
            ATTR_DATE_UNTIL: timedelta(hours=24),
        },
        blocking=True,
    )
    mock_portainer_client.images_prune.assert_called_once_with(
        endpoint_id=TEST_ENDPOINT_ID,
        until=timedelta(hours=24),
        dangling=False,
    )


@pytest.mark.parametrize(
    ("call_arguments", "expected_until", "expected_dangling"),
    [
        ({}, None, False),
        ({ATTR_DATE_UNTIL: timedelta(hours=12)}, timedelta(hours=12), False),
        (
            {ATTR_DATE_UNTIL: timedelta(hours=12), ATTR_DANGLING: True},
            timedelta(hours=12),
            True,
        ),
    ],
    ids=["no optional", "with duration", "with duration and dangling"],
)
async def test_service_prune_images(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    call_arguments: dict,
    expected_until: timedelta | None,
    expected_dangling: bool,
) -> None:
    """Test prune images service with the variants."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_IDENTIFIER)}
    )
    assert device is not None
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRUNE_IMAGES,
        {ATTR_DEVICE_ID: device.id, **call_arguments},
        blocking=True,
    )
    mock_portainer_client.images_prune.assert_called_once_with(
        endpoint_id=TEST_ENDPOINT_ID,
        until=expected_until,
        dangling=expected_dangling,
    )


@pytest.mark.parametrize(
    ("call_arguments", "extra_expected_kwargs"),
    [
        ({}, {"pull_image": False}),
        (
            {ATTR_TIMEOUT: timedelta(minutes=10)},
            {"pull_image": False, "timeout": timedelta(minutes=10)},
        ),
        (
            {ATTR_TIMEOUT: timedelta(minutes=12), ATTR_PULL_IMAGE: True},
            {"pull_image": True, "timeout": timedelta(minutes=12)},
        ),
    ],
    ids=["no optional", "with duration", "with duration and pull_image"],
)
async def test_service_recreate_container(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    call_arguments: dict,
    extra_expected_kwargs: dict,
) -> None:
    """Test recreate container service with the variants."""

    await setup_integration(hass, mock_config_entry)
    container = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_CONTAINER_DEVICE_IDENTIFIER)}
    )
    assert container is not None
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RECREATE_CONTAINER,
        {
            ATTR_CONTAINER_DEVICE_ID: container.id,
            **call_arguments,
        },
        blocking=True,
    )
    mock_portainer_client.container_recreate.assert_called_once_with(
        endpoint_id=TEST_ENDPOINT_ID,
        container_id=TEST_CONTAINER_ID,
        **extra_expected_kwargs,
    )


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (
            PortainerAuthenticationError("auth"),
            "invalid_auth_no_details",
        ),
        (
            PortainerConnectionError("conn"),
            "cannot_connect_no_details",
        ),
        (
            PortainerTimeoutError("timeout"),
            "timeout_connect_no_details",
        ),
    ],
)
async def test_service_recreate_container_portainer_exceptions(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: PortainerAuthenticationError
    | PortainerConnectionError
    | PortainerTimeoutError,
    translation_key: str,
) -> None:
    """Test recreate container service handles Portainer exceptions."""
    await setup_integration(hass, mock_config_entry)
    container = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_CONTAINER_DEVICE_IDENTIFIER)}
    )
    assert container is not None

    mock_portainer_client.container_recreate.side_effect = exception
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECREATE_CONTAINER,
            {ATTR_CONTAINER_DEVICE_ID: container.id},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    mock_portainer_client.container_recreate.assert_called_once()


async def test_service_validation_errors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Tests that the Portainer services handle bad data."""

    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_IDENTIFIER)}
    )
    assert device is not None
    container = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_CONTAINER_DEVICE_IDENTIFIER)}
    )
    assert container is not None

    with pytest.raises(MultipleInvalid, match="required key not provided"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRUNE_IMAGES,
            {},
            blocking=True,
        )
    mock_portainer_client.images_prune.assert_not_called()

    with pytest.raises(MultipleInvalid, match="value must be at least"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRUNE_IMAGES,
            {ATTR_DEVICE_ID: device.id, ATTR_DATE_UNTIL: timedelta(seconds=30)},
            blocking=True,
        )
    mock_portainer_client.images_prune.assert_not_called()

    with pytest.raises(ServiceValidationError, match="Invalid device targeted"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRUNE_IMAGES,
            {ATTR_DEVICE_ID: "invalid_device_id"},
            blocking=True,
        )
    mock_portainer_client.images_prune.assert_not_called()

    with pytest.raises(ServiceValidationError, match="Invalid device targeted"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECREATE_CONTAINER,
            {ATTR_CONTAINER_DEVICE_ID: "invalid_device_id"},
            blocking=True,
        )
    mock_portainer_client.container_recreate.assert_not_called()

    other_entry = MockConfigEntry(domain="well_no_portainer_for_sure")
    other_entry.add_to_hass(hass)
    non_portainer_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("well_no_portainer_for_sure", "some_identifier")},
    )
    with pytest.raises(ServiceValidationError, match="Invalid device targeted"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECREATE_CONTAINER,
            {ATTR_CONTAINER_DEVICE_ID: non_portainer_device.id},
            blocking=True,
        )
    mock_portainer_client.container_recreate.assert_not_called()

    with pytest.raises(ServiceValidationError, match="Invalid device targeted"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECREATE_CONTAINER,
            {ATTR_CONTAINER_DEVICE_ID: device.id},
            blocking=True,
        )
    mock_portainer_client.container_recreate.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (
            PortainerAuthenticationError("auth"),
            "An error occurred while trying to authenticate",
        ),
        (
            PortainerConnectionError("conn"),
            "An error occurred while trying to connect to the Portainer instance",
        ),
        (
            PortainerTimeoutError("timeout"),
            "A timeout occurred while trying to connect to the Portainer instance",
        ),
    ],
)
async def test_service_portainer_exceptions(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_portainer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: HomeAssistantError,
    message: str,
) -> None:
    """Test service handles Portainer exceptions."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_IDENTIFIER)}
    )

    mock_portainer_client.images_prune.side_effect = exception
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRUNE_IMAGES,
            {ATTR_DEVICE_ID: device.id},
            blocking=True,
        )
    mock_portainer_client.images_prune.assert_called_once()
