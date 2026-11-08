"""Tests for Fritz!Tools services."""

from unittest.mock import PropertyMock, patch

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzServiceError,
)
from probatio import MultipleInvalid
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser

from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.components.fritz.const import (
    CONF_ALLOW_MESH_INFO_NON_ADMIN,
    CONF_FEATURE_DEVICE_TRACKING,
    CONF_OLD_DISCOVERY,
    DOMAIN,
    MeshRoles,
)
from homeassistant.components.fritz.services import FritzService
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import (
    MOCK_HOST_ATTRIBUTES_DATA,
    MOCK_MESH_DATA,
    MOCK_SERIAL_NUMBER,
    MOCK_USER_DATA,
)


async def test_setup_services(hass: HomeAssistant) -> None:
    """Test setup of Fritz!Tools services."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    services = hass.services.async_services_for_domain(DOMAIN)
    assert services
    assert FritzService.SET_GUEST_WIFI_PASSWORD in services
    assert FritzService.DIAL in services


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
            DOMAIN, FritzService.SET_GUEST_WIFI_PASSWORD, {"device_id": device.id}
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
            DOMAIN, FritzService.SET_GUEST_WIFI_PASSWORD, {"device_id": device.id}
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
            DOMAIN, FritzService.SET_GUEST_WIFI_PASSWORD, {"device_id": device.id}
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
            DOMAIN, FritzService.SET_GUEST_WIFI_PASSWORD, {"device_id": "12345678"}
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
            FritzService.DIAL,
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
            FritzService.DIAL,
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
                FritzService.DIAL,
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
                FritzService.DIAL,
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
            FritzService.DIAL,
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
            FritzService.DIAL,
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
            FritzService.DIAL,
            {"device_id": "12345678", "number": "1234567890", "max_ring_seconds": 10},
        )
        assert not mock_async_trigger_dial.called
        assert (
            "ServiceValidationError: Failed to perform action"
            f' "{FritzService.DIAL}".'
            " Config entry for target not found" in caplog.text
        )


CACHED_HOSTS = [{"source": "cached_hosts"}]
LIVE_HOSTS = [{"source": "live_hosts"}]


@pytest.mark.parametrize(
    ("options", "cached_hosts", "hosts_fetch_calls", "expected_hosts"),
    [
        pytest.param(
            {CONF_FEATURE_DEVICE_TRACKING: False},
            CACHED_HOSTS,
            0,
            CACHED_HOSTS,
            id="no_device_tracking_hosts_cached",
        ),
        pytest.param(
            {CONF_OLD_DISCOVERY: True},
            None,
            1,
            LIVE_HOSTS,
            id="old_discovery_hosts_fetched",
        ),
    ],
)
@pytest.mark.usefixtures("fc_class_mock", "fh_class_mock", "fs_class_mock")
async def test_get_mesh_info_service_fetches_on_demand(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    options: dict[str, bool],
    cached_hosts: list[dict[str, str]] | None,
    hosts_fetch_calls: int,
    expected_hosts: list[dict[str, str]],
) -> None:
    """Test mesh info is fetched on demand when not collected by device tracking."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA, options=options)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    admin_group = await hass.auth.async_get_group(GROUP_ID_ADMIN)
    admin_user = MockUser(groups=[admin_group]).add_to_hass(hass)
    avm_wrapper = entry.runtime_data
    assert avm_wrapper.mesh_topology_raw is None

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    # Data that differs from the default mock, so a live fetch is recognizable
    live_topology = {"source": "live_topology"}

    with (
        patch.object(
            type(avm_wrapper),
            "hosts_attributes_raw",
            new_callable=PropertyMock,
            return_value=cached_hosts,
        ),
        patch.object(
            avm_wrapper.fritz_hosts,
            "get_mesh_topology",
            return_value=live_topology,
        ) as mock_get_mesh_topology,
        patch.object(
            avm_wrapper.fritz_hosts,
            "get_hosts_attributes",
            return_value=LIVE_HOSTS,
        ) as mock_get_hosts_attributes,
    ):
        result = await hass.services.async_call(
            DOMAIN,
            FritzService.GET_MESH_INFO,
            {"device_id": device.id},
            blocking=True,
            return_response=True,
            context=Context(user_id=admin_user.id),
        )

    assert result == {
        "mesh_topology": live_topology,
        "hosts_attributes": expected_hosts,
    }
    mock_get_mesh_topology.assert_called_once()
    assert mock_get_hosts_attributes.call_count == hosts_fetch_calls


@pytest.mark.usefixtures("fc_class_mock", "fh_class_mock", "fs_class_mock")
async def test_get_mesh_info_service_uses_cached_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test cached mesh info is returned without a live fetch."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    avm_wrapper = entry.runtime_data
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    # Cached data that differs from what a live fetch would return
    cached_topology = {"source": "cached_topology"}
    cached_hosts = [{"source": "cached_hosts"}]

    with (
        patch.object(
            type(avm_wrapper),
            "mesh_topology_raw",
            new_callable=PropertyMock,
            return_value=cached_topology,
        ),
        patch.object(
            type(avm_wrapper),
            "hosts_attributes_raw",
            new_callable=PropertyMock,
            return_value=cached_hosts,
        ),
        patch.object(
            avm_wrapper.fritz_hosts, "get_mesh_topology"
        ) as mock_get_mesh_topology,
        patch.object(
            avm_wrapper.fritz_hosts, "get_hosts_attributes"
        ) as mock_get_hosts_attributes,
    ):
        result = await hass.services.async_call(
            DOMAIN,
            FritzService.GET_MESH_INFO,
            {"device_id": device.id},
            blocking=True,
            return_response=True,
        )

    assert result == {
        "mesh_topology": cached_topology,
        "hosts_attributes": cached_hosts,
    }
    mock_get_mesh_topology.assert_not_called()
    mock_get_hosts_attributes.assert_not_called()


@pytest.mark.usefixtures("fc_class_mock", "fh_class_mock", "fs_class_mock")
async def test_get_mesh_info_non_admin_not_allowed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that non-admin access to get_mesh_info fails if not allowed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        options={CONF_ALLOW_MESH_INFO_NON_ADMIN: False},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    read_only_group = await hass.auth.async_get_group(GROUP_ID_READ_ONLY)
    non_admin_user = MockUser(groups=[read_only_group]).add_to_hass(hass)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            FritzService.GET_MESH_INFO,
            {"device_id": device.id},
            blocking=True,
            return_response=True,
            context=Context(user_id=non_admin_user.id),
        )


@pytest.mark.parametrize(
    ("allow_non_admin", "group_id"),
    [
        pytest.param(True, GROUP_ID_READ_ONLY, id="non_admin_allowed"),
        pytest.param(False, GROUP_ID_ADMIN, id="admin_always_allowed"),
        # No user simulates an automation or internal call.
        pytest.param(False, None, id="internal_call_always_allowed"),
    ],
)
@pytest.mark.usefixtures("fc_class_mock", "fh_class_mock", "fs_class_mock")
async def test_get_mesh_info_allowed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    allow_non_admin: bool,
    group_id: str | None,
) -> None:
    """Test get_mesh_info succeeds for permitted callers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        options={CONF_ALLOW_MESH_INFO_NON_ADMIN: allow_non_admin},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    user_id = (
        MockUser(groups=[await hass.auth.async_get_group(group_id)])
        .add_to_hass(hass)
        .id
        if group_id
        else None
    )

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    result = await hass.services.async_call(
        DOMAIN,
        FritzService.GET_MESH_INFO,
        {"device_id": device.id},
        blocking=True,
        return_response=True,
        context=Context(user_id=user_id),
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
            FritzService.GET_MESH_INFO,
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
        "mesh_side_effect",
        "hosts_side_effect",
        "expected_key",
    ),
    [
        pytest.param(
            None,
            MOCK_HOST_ATTRIBUTES_DATA,
            False,
            MeshRoles.NONE,
            None,
            None,
            "service_mesh_info_no_mesh_support",
            id="no_mesh_support",
        ),
        pytest.param(
            None,
            MOCK_HOST_ATTRIBUTES_DATA,
            True,
            MeshRoles.SLAVE,
            None,
            None,
            "service_mesh_info_slave_node",
            id="slave_node",
        ),
        pytest.param(
            None,
            MOCK_HOST_ATTRIBUTES_DATA,
            True,
            MeshRoles.NONE,
            FritzActionError("boom"),
            None,
            "service_mesh_info_slave_node",
            id="slave_node_on_demand",
        ),
        pytest.param(
            None,
            MOCK_HOST_ATTRIBUTES_DATA,
            True,
            MeshRoles.NONE,
            FritzConnectionException("boom"),
            None,
            "service_mesh_info_fetch_failed",
            id="fetch_failed",
        ),
        pytest.param(
            None,
            MOCK_HOST_ATTRIBUTES_DATA,
            True,
            MeshRoles.NONE,
            [{}],
            None,
            "service_mesh_info_fetch_failed",
            id="fetch_empty",
        ),
        pytest.param(
            MOCK_MESH_DATA,
            None,
            True,
            MeshRoles.MASTER,
            None,
            FritzConnectionException("boom"),
            "service_hosts_info_fetch_failed",
            id="hosts_fetch_failed",
        ),
    ],
)
@pytest.mark.usefixtures("fc_class_mock", "fh_class_mock", "fs_class_mock")
async def test_get_mesh_info_raises_on_missing_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mesh_topology: dict | None,
    hosts_attributes: list | None,
    has_mesh_support: bool,
    mesh_role: MeshRoles,
    mesh_side_effect: Exception | list[dict] | None,
    hosts_side_effect: Exception | None,
    expected_key: str,
) -> None:
    """Test that missing mesh topology or host attributes raise a proper error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        options={CONF_FEATURE_DEVICE_TRACKING: False},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    avm_wrapper = entry.runtime_data
    avm_wrapper.mesh_role = mesh_role
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL_NUMBER), entry.entry_id
    )
    assert device

    with (
        patch.object(
            avm_wrapper.fritz_hosts,
            "get_mesh_topology",
            return_value=mesh_topology,
            side_effect=mesh_side_effect,
        ),
        patch.object(
            avm_wrapper.fritz_hosts,
            "get_hosts_attributes",
            return_value=hosts_attributes,
            side_effect=hosts_side_effect,
        ),
        patch.object(
            type(avm_wrapper),
            "hosts_attributes_raw",
            new_callable=PropertyMock,
            return_value=None,
        ),
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
            FritzService.GET_MESH_INFO,
            {"device_id": device.id},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == expected_key
