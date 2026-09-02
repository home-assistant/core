"""Tests for Fritz!Tools services."""

from unittest.mock import PropertyMock, patch

from fritzconnection.core.exceptions import (
    FritzActionFailedError,
    FritzConnectionException,
    FritzServiceError,
)
import pytest
from voluptuous import MultipleInvalid

from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.components.fritz.const import (
    CONF_ALLOW_MESH_INFO_NON_ADMIN,
    DOMAIN,
    MeshRoles,
)
from homeassistant.components.fritz.services import (
    SERVICE_DIAL,
    SERVICE_GET_MESH_INFO,
    SERVICE_SET_GUEST_WIFI_PW,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import (
    MOCK_HOST_ATTRIBUTES_DATA,
    MOCK_MESH_DATA,
    MOCK_SERIAL_NUMBER,
    MOCK_USER_DATA,
)

from tests.common import MockConfigEntry, MockUser


async def test_setup_services(hass: HomeAssistant) -> None:
    """Test setup of Fritz!Tools services."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    services = hass.services.async_services_for_domain(DOMAIN)
    assert services
    assert SERVICE_SET_GUEST_WIFI_PW in services
    assert SERVICE_DIAL in services


async def test_service_set_guest_wifi_password(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test service set_guest_wifi_password."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device
    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password"
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": device.id}
        )
        assert mock_async_trigger_set_guest_password.called


async def test_service_set_guest_wifi_password_unknown_parameter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test service set_guest_wifi_password with unknown parameter."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password",
        side_effect=FritzServiceError("boom"),
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": device.id}
        )
        assert mock_async_trigger_set_guest_password.called
        assert "HomeAssistantError: Action or parameter unknown" in caplog.text


async def test_service_set_guest_wifi_password_service_not_supported(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test service set_guest_wifi_password with connection error."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password",
        side_effect=FritzConnectionException("boom"),
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": device.id}
        )
        assert mock_async_trigger_set_guest_password.called
        assert "HomeAssistantError: Action not supported" in caplog.text


async def test_service_set_guest_wifi_password_unloaded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test service set_guest_wifi_password."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_set_guest_password"
    ) as mock_async_trigger_set_guest_password:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_GUEST_WIFI_PW, {"device_id": "12345678"}
        )
        assert not mock_async_trigger_set_guest_password.called
        assert (
            "ServiceValidationError: Failed to perform action"
            ' "set_guest_wifi_password".'
            " Config entry for target not found" in caplog.text
        )


async def test_service_dial(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test service dial."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device
    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_dial"
    ) as mock_async_trigger_dial:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DIAL,
            {"device_id": device.id, "number": "1234567890", "max_ring_seconds": 10},
        )
        assert mock_async_trigger_dial.called
        assert mock_async_trigger_dial.call_args.kwargs == {"max_ring_seconds": 10}
        assert mock_async_trigger_dial.call_args.args == ("1234567890",)


async def test_service_dial_unknown_parameter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test service dial with unknown parameters."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_dial",
        side_effect=FritzServiceError("boom"),
    ) as mock_async_trigger_dial:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DIAL,
            {"device_id": device.id, "number": "1234567890", "max_ring_seconds": 10},
        )
        assert mock_async_trigger_dial.called
        assert "HomeAssistantError: Action or parameter unknown" in caplog.text


async def test_service_dial_wrong_parameter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test service dial with unknown parameters."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_dial",
    ) as mock_async_trigger_dial:
        with pytest.raises(MultipleInvalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DIAL,
                {
                    "device_id": device.id,
                    "number": "1234567890",
                    "max_ring_seconds": "",
                },
            )
        assert not mock_async_trigger_dial.called
    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_dial",
    ) as mock_async_trigger_dial:
        with pytest.raises(MultipleInvalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DIAL,
                {
                    "device_id": device.id,
                    "number": "1234567890",
                    "max_ring_seconds": 0,
                },
            )
        assert not mock_async_trigger_dial.called


async def test_service_dial_service_not_supported(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test service dial with connection error."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_dial",
        side_effect=FritzConnectionException("boom"),
    ) as mock_async_trigger_dial:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DIAL,
            {"device_id": device.id, "number": "1234567890", "max_ring_seconds": 10},
        )
        assert mock_async_trigger_dial.called
        assert "HomeAssistantError: Action not supported" in caplog.text


async def test_service_dial_failed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test dial service when the dial help is disabled."""
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_dial",
        side_effect=FritzActionFailedError("boom"),
    ) as mock_async_trigger_dial:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DIAL,
            {"device_id": device.id, "number": "1234567890", "max_ring_seconds": 10},
        )
        assert mock_async_trigger_dial.called
        assert (
            "HomeAssistantError: Failed to dial, check if the"
            " click to dial service of the FRITZ!Box is activated" in caplog.text
        )


async def test_service_dial_unloaded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fs_class_mock,
) -> None:
    """Test service dial."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_trigger_dial"
    ) as mock_async_trigger_dial:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DIAL,
            {"device_id": "12345678", "number": "1234567890", "max_ring_seconds": 10},
        )
        assert not mock_async_trigger_dial.called
        assert (
            "ServiceValidationError: Failed to perform action"
            f' "{SERVICE_DIAL}".'
            " Config entry for target not found" in caplog.text
        )


async def test_get_mesh_info_service_returns_stored_values(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test entry services return stored values per config entry."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
    )
    assert device

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MESH_INFO,
        {"device_id": device.id},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "mesh_topology": MOCK_MESH_DATA,
        "hosts_attributes": MOCK_HOST_ATTRIBUTES_DATA,
    }


@pytest.mark.parametrize(
    ("allow_non_admin", "expect_error"),
    [
        pytest.param(False, True, id="non_admin_not_allowed"),
        pytest.param(True, False, id="non_admin_allowed"),
    ],
)
async def test_get_mesh_info_non_admin_permission(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    allow_non_admin: bool,
    expect_error: bool,
) -> None:
    """Test that non-admin access to get_mesh_info depends on the option."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        options={CONF_ALLOW_MESH_INFO_NON_ADMIN: allow_non_admin},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    read_only_group = await hass.auth.async_get_group(GROUP_ID_READ_ONLY)
    non_admin_user = MockUser(groups=[read_only_group]).add_to_hass(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
    )
    assert device

    if expect_error:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_GET_MESH_INFO,
                {"device_id": device.id},
                blocking=True,
                return_response=True,
                context=Context(user_id=non_admin_user.id),
            )
    else:
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MESH_INFO,
            {"device_id": device.id},
            blocking=True,
            return_response=True,
            context=Context(user_id=non_admin_user.id),
        )
        assert result == {
            "mesh_topology": MOCK_MESH_DATA,
            "hosts_attributes": MOCK_HOST_ATTRIBUTES_DATA,
        }


async def test_get_mesh_info_admin_always_allowed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test that admin users can always call get_mesh_info regardless of the option."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        options={CONF_ALLOW_MESH_INFO_NON_ADMIN: False},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    admin_group = await hass.auth.async_get_group(GROUP_ID_ADMIN)
    admin_user = MockUser(groups=[admin_group]).add_to_hass(hass)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
    )
    assert device

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MESH_INFO,
        {"device_id": device.id},
        blocking=True,
        return_response=True,
        context=Context(user_id=admin_user.id),
    )
    assert result == {
        "mesh_topology": MOCK_MESH_DATA,
        "hosts_attributes": MOCK_HOST_ATTRIBUTES_DATA,
    }


async def test_get_mesh_info_internal_call_always_allowed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test that internal calls (no user_id) are always permitted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        options={CONF_ALLOW_MESH_INFO_NON_ADMIN: False},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
    )
    assert device

    # No context / no user_id simulates an automation or internal call.
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MESH_INFO,
        {"device_id": device.id},
        blocking=True,
        return_response=True,
    )
    assert result == {
        "mesh_topology": MOCK_MESH_DATA,
        "hosts_attributes": MOCK_HOST_ATTRIBUTES_DATA,
    }


async def test_get_mesh_info_service_raises_on_invalid_entry(
    hass: HomeAssistant,
) -> None:
    """Service should raise when no matching device target is found."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MESH_INFO,
            {"device_id": "non_existent_device_id"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    (
        "mesh_topology",
        "hosts_attributes",
        "has_mesh_support",
        "mesh_role",
        "expected_key",
    ),
    [
        pytest.param(
            None,
            MOCK_HOST_ATTRIBUTES_DATA,
            False,
            MeshRoles.NONE,
            "service_mesh_info_no_mesh_support",
            id="no_mesh_support",
        ),
        pytest.param(
            None,
            MOCK_HOST_ATTRIBUTES_DATA,
            True,
            MeshRoles.SLAVE,
            "service_mesh_info_slave_node",
            id="slave_node",
        ),
        pytest.param(
            None,
            MOCK_HOST_ATTRIBUTES_DATA,
            True,
            MeshRoles.NONE,
            "service_mesh_info_fetch_failed",
            id="fetch_failed",
        ),
        pytest.param(
            MOCK_MESH_DATA,
            None,
            True,
            MeshRoles.MASTER,
            "service_hosts_info_fetch_failed",
            id="hosts_fetch_failed",
        ),
    ],
)
async def test_get_mesh_info_raises_on_missing_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    mesh_topology: dict | None,
    hosts_attributes: list | None,
    has_mesh_support: bool,
    mesh_role: MeshRoles,
    expected_key: str,
) -> None:
    """Test that missing mesh topology or host attributes raise a proper error."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    avm_wrapper = entry.runtime_data
    avm_wrapper._mesh_topology_raw = mesh_topology
    avm_wrapper._hosts_attributes_raw = hosts_attributes
    avm_wrapper.mesh_role = mesh_role

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_SERIAL_NUMBER)}
    )
    assert device

    with (
        patch.object(
            type(avm_wrapper.fritz_status),
            "device_has_mesh_support",
            new_callable=PropertyMock,
            return_value=has_mesh_support,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MESH_INFO,
            {"device_id": device.id},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == expected_key
