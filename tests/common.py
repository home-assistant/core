"""Test the helper method for writing tests."""

from __future__ import annotations

import asyncio
from collections.abc import (
    AsyncGenerator,
    Callable,
    Coroutine,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from contextlib import asynccontextmanager, contextmanager, suppress
from datetime import UTC, datetime, timedelta
from enum import Enum, StrEnum
import functools as ft
from functools import lru_cache
from io import StringIO
import json
import logging
import os
import pathlib
import time
from types import FrameType, ModuleType
from typing import Any, Literal, NoReturn
from unittest.mock import AsyncMock, Mock, patch

from aiohttp.test_utils import unused_port as get_test_instance_port  # noqa: F401
from annotatedyaml import load_yaml_dict, loader as yaml_loader
import attr
import pytest
from syrupy import SnapshotAssertion
import voluptuous as vol

from homeassistant import auth, bootstrap, config_entries, loader
from homeassistant.auth import (
    auth_store,
    models as auth_models,
    permissions as auth_permissions,
    providers as auth_providers,
)
from homeassistant.auth.permissions import system_policies
from homeassistant.components import device_automation, persistent_notification as pn
from homeassistant.components.device_automation import (  # noqa: F401
    _async_get_device_automation_capabilities as async_get_device_automation_capabilities,
)
from homeassistant.components.logger import (
    DOMAIN as LOGGER_DOMAIN,
    SERVICE_SET_LEVEL,
    _clear_logger_overwrites,
)
from homeassistant.config import IntegrationConfigInfo, async_process_component_config
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    DEVICE_DEFAULT_NAME,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import (
    CoreState,
    Event,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    State,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    device_registry as dr,
    entity,
    entity_platform,
    entity_registry as er,
    event,
    floor_registry as fr,
    intent,
    issue_registry as ir,
    label_registry as lr,
    restore_state as rs,
    storage,
    translation,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.json import JSONEncoder, _orjson_default_encoder, json_dumps
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, ulid as ulid_util, uuid as uuid_util
from homeassistant.util.async_ import (
    _SHUTDOWN_RUN_CALLBACK_THREADSAFE,
    get_scheduled_timer_handles,
    run_callback_threadsafe,
)
from homeassistant.util.event_type import EventType
from homeassistant.util.json import (
    JsonArrayType,
    JsonObjectType,
    JsonValueType,
    json_loads,
    json_loads_array,
    json_loads_object,
)
from homeassistant.util.signal_type import SignalType
from homeassistant.util.unit_system import METRIC_SYSTEM

from .testing_config.custom_components.test_constant_deprecation import (
    import_deprecated_constant,
)

_LOGGER = logging.getLogger(__name__)
INSTANCES = []
CLIENT_ID = "https://example.com/app"
CLIENT_REDIRECT_URI = "https://example.com/app/callback"


class QualityScaleStatus(StrEnum):
    """Source of core configuration."""

    DONE = "done"
    EXEMPT = "exempt"
    TODO = "todo"


async def async_get_device_automations(
    hass: HomeAssistant,
    automation_type: device_automation.DeviceAutomationType,
    device_id: str,
) -> Any:
    """Get a device automation for a single device id."""
    automations = await device_automation.async_get_device_automations(
        hass, automation_type, [device_id]
    )
    return automations.get(device_id)


def threadsafe_callback_factory(func):
    """Create threadsafe functions out of callbacks.

    Callback needs to have `hass` as first argument.
    """

    @ft.wraps(func)
    def threadsafe(*args, **kwargs):
        """Call func threadsafe."""
        hass = args[0]
        return run_callback_threadsafe(
            hass.loop, ft.partial(func, *args, **kwargs)
        ).result()

    return threadsafe


def threadsafe_coroutine_factory(func):
    """Create threadsafe functions out of coroutine.

    Callback needs to have `hass` as first argument.
    """

    @ft.wraps(func)
    def threadsafe(*args, **kwargs):
        """Call func threadsafe."""
        hass = args[0]
        return asyncio.run_coroutine_threadsafe(
            func(*args, **kwargs), hass.loop
        ).result()

    return threadsafe


def get_test_config_dir(*add_path):
    """Return a path to a test config dir."""
    return os.path.join(os.path.dirname(__file__), "testing_config", *add_path)


class StoreWithoutWriteLoad[_T: (Mapping[str, Any] | Sequence[Any])](storage.Store[_T]):
    """Fake store that does not write or load. Used for testing."""

    async def async_save(self, *args: Any, **kwargs: Any) -> None:
        """Save the data.

        This function is mocked out in tests.
        """

    @callback
    def async_save_delay(self, *args: Any, **kwargs: Any) -> None:
        """Save data with an optional delay.

        This function is mocked out in tests.
        """


@asynccontextmanager
async def async_test_home_assistant(
    event_loop: asyncio.AbstractEventLoop | None = None,
    load_registries: bool = True,
    config_dir: str | None = None,
    initial_state: CoreState = CoreState.running,
) -> AsyncGenerator[HomeAssistant]:
    """Return a Home Assistant object pointing at test config dir."""
    hass = HomeAssistant(config_dir or get_test_config_dir())
    store = auth_store.AuthStore(hass)
    hass.auth = auth.AuthManager(hass, store, {}, {})
    ensure_auth_manager_loaded(hass.auth)
    INSTANCES.append(hass)

    orig_async_add_job = hass.async_add_job
    orig_async_add_executor_job = hass.async_add_executor_job
    orig_async_create_task_internal = hass.async_create_task_internal
    orig_tz = dt_util.get_default_time_zone()

    def async_add_job(target, *args, eager_start: bool = False):
        """Add job."""
        check_target = target
        while isinstance(check_target, ft.partial):
            check_target = check_target.func

        if isinstance(check_target, Mock) and not isinstance(target, AsyncMock):
            fut = asyncio.Future()
            fut.set_result(target(*args))
            return fut

        return orig_async_add_job(target, *args, eager_start=eager_start)

    def async_add_executor_job(target, *args):
        """Add executor job."""
        check_target = target
        while isinstance(check_target, ft.partial):
            check_target = check_target.func

        if isinstance(check_target, Mock):
            fut = asyncio.Future()
            fut.set_result(target(*args))
            return fut

        return orig_async_add_executor_job(target, *args)

    def async_create_task_internal(coroutine, name=None, eager_start=True):
        """Create task."""
        if isinstance(coroutine, Mock) and not isinstance(coroutine, AsyncMock):
            fut = asyncio.Future()
            fut.set_result(None)
            return fut

        return orig_async_create_task_internal(coroutine, name, eager_start)

    hass.async_add_job = async_add_job
    hass.async_add_executor_job = async_add_executor_job
    hass.async_create_task_internal = async_create_task_internal

    hass.data[loader.DATA_CUSTOM_COMPONENTS] = {}

    hass.config.location_name = "test home"
    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743
    hass.config.elevation = 0
    await hass.config.async_set_time_zone("US/Pacific")
    hass.config.units = METRIC_SYSTEM
    hass.config.media_dirs = {"local": get_test_config_dir("media")}
    hass.config.skip_pip = True
    hass.config.skip_pip_packages = []

    hass.config_entries = config_entries.ConfigEntries(
        hass,
        {
            "_": (
                "Not empty or else some bad checks for hass config in discovery.py"
                " breaks"
            )
        },
    )
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        hass.config_entries._async_shutdown,
    )

    # Load the registries
    entity.async_setup(hass)
    loader.async_setup(hass)

    # setup translation cache instead of calling translation.async_setup(hass)
    hass.data[translation.TRANSLATION_FLATTEN_CACHE] = translation._TranslationCache(
        hass
    )
    if load_registries:
        with (
            patch.object(StoreWithoutWriteLoad, "async_load", return_value=None),
            patch(
                "homeassistant.helpers.area_registry.AreaRegistryStore",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.device_registry.DeviceRegistryStore",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.entity_registry.EntityRegistryStore",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.storage.Store",  # Floor & label registry are different
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.issue_registry.IssueRegistryStore",
                StoreWithoutWriteLoad,
            ),
            patch(
                "homeassistant.helpers.restore_state.RestoreStateData.async_setup_dump",
                return_value=None,
            ),
            patch(
                "homeassistant.helpers.restore_state.start.async_at_start",
            ),
        ):
            await ar.async_load(hass)
            await cr.async_load(hass)
            await dr.async_load(hass)
            await er.async_load(hass)
            await fr.async_load(hass)
            await ir.async_load(hass)
            await lr.async_load(hass)
            await rs.async_load(hass)
        hass.data[bootstrap.DATA_REGISTRIES_LOADED] = None

    hass.set_state(initial_state)

    @callback
    def clear_instance(event):
        """Clear global instance."""
        # Give aiohttp one loop iteration to close
        hass.loop.call_soon(INSTANCES.remove, hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, clear_instance)

    try:
        yield hass
    finally:
        # Restore timezone, it is set when creating the hass object
        dt_util.set_default_time_zone(orig_tz)
        # Remove loop shutdown indicator to not interfere with additional hass objects
        with suppress(AttributeError):
            delattr(hass.loop, _SHUTDOWN_RUN_CALLBACK_THREADSAFE)


def async_mock_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    schema: vol.Schema | None = None,
    response: ServiceResponse = None,
    supports_response: SupportsResponse | None = None,
    raise_exception: Exception | None = None,
) -> list[ServiceCall]:
    """Set up a fake service & return a calls log list to this service."""
    calls = []

    @callback
    def mock_service_log(call):
        """Mock service call."""
        calls.append(call)
        if raise_exception is not None:
            raise raise_exception
        return response

    if supports_response is None:
        if response is not None:
            supports_response = SupportsResponse.OPTIONAL
        else:
            supports_response = SupportsResponse.NONE

    hass.services.async_register(
        domain,
        service,
        mock_service_log,
        schema=schema,
        supports_response=supports_response,
    )

    return calls


mock_service = threadsafe_callback_factory(async_mock_service)


@callback
def async_mock_intent(hass: HomeAssistant, intent_typ: str) -> list[intent.Intent]:
    """Set up a fake intent handler."""
    intents: list[intent.Intent] = []

    class MockIntentHandler(intent.IntentHandler):
        intent_type = intent_typ

        async def async_handle(
            self, intent_obj: intent.Intent
        ) -> intent.IntentResponse:
            """Handle the intent."""
            intents.append(intent_obj)
            return intent_obj.create_response()

    intent.async_register(hass, MockIntentHandler())

    return intents


class MockMqttReasonCode:
    """Class to fake a MQTT ReasonCode."""

    value: int
    is_failure: bool

    def __init__(
        self, value: int = 0, is_failure: bool = False, name: str = "Success"
    ) -> None:
        """Initialize the mock reason code."""
        self.value = value
        self.is_failure = is_failure
        self._name = name

    def getName(self) -> str:
        """Return the name of the reason code."""
        return self._name


@callback
def async_fire_mqtt_message(
    hass: HomeAssistant,
    topic: str,
    payload: bytes | str,
    qos: int = 0,
    retain: bool = False,
) -> None:
    """Fire the MQTT message."""
    # Local import to avoid processing MQTT modules when running a testcase
    # which does not use MQTT.

    # pylint: disable-next=import-outside-toplevel
    from paho.mqtt.client import MQTTMessage

    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.mqtt import MqttData

    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    msg = MQTTMessage(topic=topic.encode("utf-8"))
    msg.payload = payload
    msg.qos = qos
    msg.retain = retain
    msg.timestamp = time.monotonic()

    mqtt_data: MqttData = hass.data["mqtt"]
    assert mqtt_data.client
    mqtt_data.client._async_mqtt_on_message(Mock(), None, msg)


fire_mqtt_message = threadsafe_callback_factory(async_fire_mqtt_message)


@callback
def async_fire_time_changed_exact(
    hass: HomeAssistant, datetime_: datetime | None = None, fire_all: bool = False
) -> None:
    """Fire a time changed event at an exact microsecond.

    Consider that it is not possible to actually achieve an exact
    microsecond in production as the event loop is not precise enough.
    If your code relies on this level of precision, consider a different
    approach, as this is only for testing.
    """
    if datetime_ is None:
        utc_datetime = datetime.now(UTC)
    else:
        utc_datetime = dt_util.as_utc(datetime_)

    _async_fire_time_changed(hass, utc_datetime, fire_all)


@callback
def async_fire_time_changed(
    hass: HomeAssistant, datetime_: datetime | None = None, fire_all: bool = False
) -> None:
    """Fire a time changed event.

    If called within the first 500  ms of a second, time will be bumped to exactly
    500 ms to match the async_track_utc_time_change event listeners and
    DataUpdateCoordinator which spreads all updates between 0.05..0.50.
    Background in PR https://github.com/home-assistant/core/pull/82233

    As asyncio is cooperative, we can't guarantee that the event loop will
    run an event at the exact time we want. If you need to fire time changed
    for an exact microsecond, use async_fire_time_changed_exact.
    """
    if datetime_ is None:
        utc_datetime = datetime.now(UTC)
    else:
        utc_datetime = dt_util.as_utc(datetime_)

    # Increase the mocked time by 0.5 s to account for up to 0.5 s delay
    # added to events scheduled by update_coordinator and async_track_time_interval
    utc_datetime += timedelta(microseconds=event.RANDOM_MICROSECOND_MAX)

    _async_fire_time_changed(hass, utc_datetime, fire_all)


_MONOTONIC_RESOLUTION = time.get_clock_info("monotonic").resolution


@callback
def _async_fire_time_changed(
    hass: HomeAssistant, utc_datetime: datetime | None, fire_all: bool
) -> None:
    timestamp = utc_datetime.timestamp()
    for task in list(get_scheduled_timer_handles(hass.loop)):
        if not isinstance(task, asyncio.TimerHandle):
            continue
        if task.cancelled():
            continue

        mock_seconds_into_future = timestamp - time.time()
        future_seconds = task.when() - (hass.loop.time() + _MONOTONIC_RESOLUTION)

        if fire_all or mock_seconds_into_future >= future_seconds:
            with (
                patch(
                    "homeassistant.helpers.event.time_tracker_utcnow",
                    return_value=utc_datetime,
                ),
                patch(
                    "homeassistant.helpers.event.time_tracker_timestamp",
                    return_value=timestamp,
                ),
            ):
                task._run()
                task.cancel()


fire_time_changed = threadsafe_callback_factory(async_fire_time_changed)


def get_fixture_path(filename: str, integration: str | None = None) -> pathlib.Path:
    """Get path of fixture."""
    if integration is None and "/" in filename and not filename.startswith("helpers/"):
        integration, filename = filename.split("/", 1)

    if integration is None:
        return pathlib.Path(__file__).parent.joinpath("fixtures", filename)

    return pathlib.Path(__file__).parent.joinpath(
        "components", integration, "fixtures", filename
    )


@lru_cache
def load_fixture(filename: str, integration: str | None = None) -> str:
    """Load a fixture."""
    return get_fixture_path(filename, integration).read_text(encoding="utf8")


def load_json_value_fixture(
    filename: str, integration: str | None = None
) -> JsonValueType:
    """Load a JSON value from a fixture."""
    return json_loads(load_fixture(filename, integration))


def load_json_array_fixture(
    filename: str, integration: str | None = None
) -> JsonArrayType:
    """Load a JSON array from a fixture."""
    return json_loads_array(load_fixture(filename, integration))


def load_json_object_fixture(
    filename: str, integration: str | None = None
) -> JsonObjectType:
    """Load a JSON object from a fixture."""
    return json_loads_object(load_fixture(filename, integration))


def json_round_trip(obj: Any) -> Any:
    """Round trip an object to JSON."""
    return json_loads(json_dumps(obj))


def mock_state_change_event(
    hass: HomeAssistant, new_state: State, old_state: State | None = None
) -> None:
    """Mock state change event."""
    event_data = {
        "entity_id": new_state.entity_id,
        "new_state": new_state,
        "old_state": old_state,
    }
    hass.bus.fire(EVENT_STATE_CHANGED, event_data, context=new_state.context)


@callback
def mock_component(hass: HomeAssistant, component: str) -> None:
    """Mock a component is setup."""
    if component in hass.config.components:
        raise AssertionError(f"Integration {component} is already setup")

    hass.config.components.add(component)


def mock_registry(
    hass: HomeAssistant,
    mock_entries: dict[str, er.RegistryEntry] | None = None,
) -> er.EntityRegistry:
    """Mock the Entity Registry.

    This should only be used if you need to mock/re-stage a clean mocked
    entity registry in your current hass object. It can be useful to,
    for example, pre-load the registry with items.

    This mock will thus replace the existing registry in the running hass.

    If you just need to access the existing registry, use the `entity_registry`
    fixture instead.
    """
    registry = er.EntityRegistry(hass)
    if mock_entries is None:
        mock_entries = {}
    registry.deleted_entities = {}
    registry.entities = er.EntityRegistryItems()
    registry._entities_data = registry.entities.data
    for key, entry in mock_entries.items():
        registry.entities[key] = entry

    hass.data[er.DATA_REGISTRY] = registry
    er.async_get.cache_clear()
    return registry


@attr.s(frozen=True, kw_only=True, slots=True)
class RegistryEntryWithDefaults(er.RegistryEntry):
    """Helper to create a registry entry with defaults."""

    capabilities: Mapping[str, Any] | None = attr.ib(default=None)
    config_entry_id: str | None = attr.ib(default=None)
    config_subentry_id: str | None = attr.ib(default=None)
    created_at: datetime = attr.ib(factory=dt_util.utcnow)
    device_id: str | None = attr.ib(default=None)
    disabled_by: er.RegistryEntryDisabler | None = attr.ib(default=None)
    entity_category: er.EntityCategory | None = attr.ib(default=None)
    hidden_by: er.RegistryEntryHider | None = attr.ib(default=None)
    id: str = attr.ib(
        default=None,
        converter=attr.converters.default_if_none(factory=uuid_util.random_uuid_hex),  # type: ignore[misc]
    )
    has_entity_name: bool = attr.ib(default=False)
    options: er.ReadOnlyEntityOptionsType = attr.ib(
        default=None, converter=er._protect_entity_options
    )
    original_device_class: str | None = attr.ib(default=None)
    original_icon: str | None = attr.ib(default=None)
    original_name: str | None = attr.ib(default=None)
    supported_features: int = attr.ib(default=0)
    translation_key: str | None = attr.ib(default=None)
    unit_of_measurement: str | None = attr.ib(default=None)


def mock_area_registry(
    hass: HomeAssistant, mock_entries: dict[str, ar.AreaEntry] | None = None
) -> ar.AreaRegistry:
    """Mock the Area Registry.

    This should only be used if you need to mock/re-stage a clean mocked
    area registry in your current hass object. It can be useful to,
    for example, pre-load the registry with items.

    This mock will thus replace the existing registry in the running hass.

    If you just need to access the existing registry, use the `area_registry`
    fixture instead.
    """
    registry = ar.AreaRegistry(hass)
    registry.areas = ar.AreaRegistryItems()
    for key, entry in mock_entries.items():
        registry.areas[key] = entry

    hass.data[ar.DATA_REGISTRY] = registry
    ar.async_get.cache_clear()
    return registry


def mock_device_registry(
    hass: HomeAssistant,
    mock_entries: dict[str, dr.DeviceEntry] | None = None,
) -> dr.DeviceRegistry:
    """Mock the Device Registry.

    This should only be used if you need to mock/re-stage a clean mocked
    device registry in your current hass object. It can be useful to,
    for example, pre-load the registry with items.

    This mock will thus replace the existing registry in the running hass.

    If you just need to access the existing registry, use the `device_registry`
    fixture instead.
    """
    registry = dr.DeviceRegistry(hass)
    registry.devices = dr.ActiveDeviceRegistryItems()
    registry._device_data = registry.devices.data
    if mock_entries is None:
        mock_entries = {}
    for key, entry in mock_entries.items():
        registry.devices[key] = entry
    registry.deleted_devices = dr.DeviceRegistryItems()

    hass.data[dr.DATA_REGISTRY] = registry
    dr.async_get.cache_clear()
    return registry


class MockGroup(auth_models.Group):
    """Mock a group in Home Assistant."""

    def __init__(self, id: str | None = None, name: str | None = "Mock Group") -> None:
        """Mock a group."""
        kwargs = {"name": name, "policy": system_policies.ADMIN_POLICY}
        if id is not None:
            kwargs["id"] = id

        super().__init__(**kwargs)

    def add_to_hass(self, hass: HomeAssistant) -> MockGroup:
        """Test helper to add entry to hass."""
        return self.add_to_auth_manager(hass.auth)

    def add_to_auth_manager(self, auth_mgr: auth.AuthManager) -> MockGroup:
        """Test helper to add entry to hass."""
        ensure_auth_manager_loaded(auth_mgr)
        auth_mgr._store._groups[self.id] = self
        return self


class MockUser(auth_models.User):
    """Mock a user in Home Assistant."""

    def __init__(
        self,
        id: str | None = None,
        is_owner: bool = False,
        is_active: bool = True,
        name: str | None = "Mock User",
        system_generated: bool = False,
        groups: list[auth_models.Group] | None = None,
    ) -> None:
        """Initialize mock user."""
        kwargs = {
            "is_owner": is_owner,
            "is_active": is_active,
            "name": name,
            "system_generated": system_generated,
            "groups": groups or [],
            "perm_lookup": None,
        }
        if id is not None:
            kwargs["id"] = id
        super().__init__(**kwargs)

    def add_to_hass(self, hass: HomeAssistant) -> MockUser:
        """Test helper to add entry to hass."""
        return self.add_to_auth_manager(hass.auth)

    def add_to_auth_manager(self, auth_mgr: auth.AuthManager) -> MockUser:
        """Test helper to add entry to hass."""
        ensure_auth_manager_loaded(auth_mgr)
        auth_mgr._store._users[self.id] = self
        return self

    def mock_policy(self, policy: auth_permissions.PolicyType) -> None:
        """Mock a policy for a user."""
        self.permissions = auth_permissions.PolicyPermissions(policy, self.perm_lookup)


async def register_auth_provider(
    hass: HomeAssistant, config: ConfigType
) -> auth_providers.AuthProvider:
    """Register an auth provider."""
    provider = await auth_providers.auth_provider_from_config(
        hass, hass.auth._store, config
    )
    assert provider is not None, "Invalid config specified"
    key = (provider.type, provider.id)
    providers = hass.auth._providers

    if key in providers:
        raise ValueError("Provider already registered")

    providers[key] = provider
    return provider


@callback
def ensure_auth_manager_loaded(auth_mgr: auth.AuthManager) -> None:
    """Ensure an auth manager is considered loaded."""
    store = auth_mgr._store
    if store._users is None:
        store._set_defaults()


class MockModule:
    """Representation of a fake module."""

    def __init__(
        self,
        domain: str | None = None,
        *,
        dependencies: list[str] | None = None,
        setup: Callable[[HomeAssistant, ConfigType], bool] | None = None,
        requirements: list[str] | None = None,
        config_schema: vol.Schema | None = None,
        platform_schema: vol.Schema | None = None,
        platform_schema_base: vol.Schema | None = None,
        async_setup: Callable[[HomeAssistant, ConfigType], Coroutine[Any, Any, bool]]
        | None = None,
        async_setup_entry: Callable[
            [HomeAssistant, ConfigEntry], Coroutine[Any, Any, bool]
        ]
        | None = None,
        async_unload_entry: Callable[
            [HomeAssistant, ConfigEntry], Coroutine[Any, Any, bool]
        ]
        | None = None,
        async_migrate_entry: Callable[
            [HomeAssistant, ConfigEntry], Coroutine[Any, Any, bool]
        ]
        | None = None,
        async_remove_entry: Callable[
            [HomeAssistant, ConfigEntry], Coroutine[Any, Any, None]
        ]
        | None = None,
        partial_manifest: dict[str, Any] | None = None,
        async_remove_config_entry_device: Callable[
            [HomeAssistant, ConfigEntry, dr.DeviceEntry], Coroutine[Any, Any, bool]
        ]
        | None = None,
    ) -> None:
        """Initialize the mock module."""
        self.__name__ = f"homeassistant.components.{domain}"
        self.__file__ = f"homeassistant/components/{domain}"
        self.DOMAIN = domain
        self.DEPENDENCIES = dependencies or []
        self.REQUIREMENTS = requirements or []
        # Overlay to be used when generating manifest from this module
        self._partial_manifest = partial_manifest

        if config_schema is not None:
            self.CONFIG_SCHEMA = config_schema

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema

        if platform_schema_base is not None:
            self.PLATFORM_SCHEMA_BASE = platform_schema_base

        if setup:
            # We run this in executor, wrap it in function
            # pylint: disable-next=unnecessary-lambda
            self.setup = lambda *args: setup(*args)

        if async_setup is not None:
            self.async_setup = async_setup

        if setup is None and async_setup is None:
            self.async_setup = AsyncMock(return_value=True)

        if async_setup_entry is not None:
            self.async_setup_entry = async_setup_entry

        if async_unload_entry is not None:
            self.async_unload_entry = async_unload_entry

        if async_migrate_entry is not None:
            self.async_migrate_entry = async_migrate_entry

        if async_remove_entry is not None:
            self.async_remove_entry = async_remove_entry

        if async_remove_config_entry_device is not None:
            self.async_remove_config_entry_device = async_remove_config_entry_device

    def mock_manifest(self):
        """Generate a mock manifest to represent this module."""
        return {
            **loader.manifest_from_legacy_module(self.DOMAIN, self),
            **(self._partial_manifest or {}),
        }


class MockPlatform:
    """Provide a fake platform."""

    __name__ = "homeassistant.components.light.bla"
    __file__ = "homeassistant/components/blah/light"

    def __init__(
        self,
        *,
        setup_platform: Callable[
            [HomeAssistant, ConfigType, AddEntitiesCallback, DiscoveryInfoType | None],
            None,
        ]
        | None = None,
        dependencies: list[str] | None = None,
        platform_schema: vol.Schema | None = None,
        async_setup_platform: Callable[
            [HomeAssistant, ConfigType, AddEntitiesCallback, DiscoveryInfoType | None],
            Coroutine[Any, Any, None],
        ]
        | None = None,
        async_setup_entry: Callable[
            [HomeAssistant, ConfigEntry, AddEntitiesCallback], Coroutine[Any, Any, None]
        ]
        | None = None,
        scan_interval: timedelta | None = None,
    ) -> None:
        """Initialize the platform."""
        self.DEPENDENCIES = dependencies or []

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema

        if scan_interval is not None:
            self.SCAN_INTERVAL = scan_interval

        if setup_platform is not None:
            # We run this in executor, wrap it in function
            # pylint: disable-next=unnecessary-lambda
            self.setup_platform = lambda *args: setup_platform(*args)

        if async_setup_platform is not None:
            self.async_setup_platform = async_setup_platform

        if async_setup_entry is not None:
            self.async_setup_entry = async_setup_entry

        if setup_platform is None and async_setup_platform is None:
            self.async_setup_platform = AsyncMock(return_value=None)


class MockEntityPlatform(entity_platform.EntityPlatform):
    """Mock class with some mock defaults."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger=None,
        domain="test_domain",
        platform_name="test_platform",
        platform=None,
        scan_interval=timedelta(seconds=15),
        entity_namespace=None,
    ) -> None:
        """Initialize a mock entity platform."""
        if logger is None:
            logger = logging.getLogger("homeassistant.helpers.entity_platform")

        # Otherwise the constructor will blow up.
        if isinstance(platform, Mock) and isinstance(platform.PARALLEL_UPDATES, Mock):
            platform.PARALLEL_UPDATES = 0

        super().__init__(
            hass=hass,
            logger=logger,
            domain=domain,
            platform_name=platform_name,
            platform=platform,
            scan_interval=scan_interval,
            entity_namespace=entity_namespace,
        )

        @callback
        def _async_on_stop(_: Event) -> None:
            self.async_shutdown()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_stop)


class MockToggleEntity(entity.ToggleEntity):
    """Provide a mock toggle device."""

    def __init__(self, name: str | None, state: Literal["on", "off"] | None) -> None:
        """Initialize the mock entity."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self.calls: list[tuple[str, dict[str, Any]]] = []

    @property
    def name(self) -> str:
        """Return the name of the entity if any."""
        self.calls.append(("name", {}))
        return self._name

    @property
    def state(self) -> Literal["on", "off"] | None:
        """Return the state of the entity if any."""
        self.calls.append(("state", {}))
        return self._state

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        self.calls.append(("is_on", {}))
        return self._state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.calls.append(("turn_on", kwargs))
        self._state = STATE_ON

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.calls.append(("turn_off", kwargs))
        self._state = STATE_OFF

    def last_call(self, method: str | None = None) -> tuple[str, dict[str, Any]]:
        """Return the last call."""
        if not self.calls:
            return None
        if method is None:
            return self.calls[-1]
        try:
            return next(call for call in reversed(self.calls) if call[0] == method)
        except StopIteration:
            return None


class MockConfigEntry(config_entries.ConfigEntry):
    """Helper for creating config entries that adds some defaults."""

    def __init__(
        self,
        *,
        data=None,
        disabled_by=None,
        discovery_keys=None,
        domain="test",
        entry_id=None,
        minor_version=1,
        options=None,
        pref_disable_new_entities=None,
        pref_disable_polling=None,
        reason=None,
        source=config_entries.SOURCE_USER,
        state=None,
        subentries_data=None,
        title="Mock Title",
        unique_id=None,
        version=1,
    ) -> None:
        """Initialize a mock config entry."""
        discovery_keys = discovery_keys or {}
        kwargs = {
            "data": data or {},
            "disabled_by": disabled_by,
            "discovery_keys": discovery_keys,
            "domain": domain,
            "entry_id": entry_id or ulid_util.ulid_now(),
            "minor_version": minor_version,
            "options": options or {},
            "pref_disable_new_entities": pref_disable_new_entities,
            "pref_disable_polling": pref_disable_polling,
            "subentries_data": subentries_data or (),
            "title": title,
            "unique_id": unique_id,
            "version": version,
        }
        if source is not None:
            kwargs["source"] = source
        if state is not None:
            kwargs["state"] = state
        super().__init__(**kwargs)
        if reason is not None:
            object.__setattr__(self, "reason", reason)

    def add_to_hass(self, hass: HomeAssistant) -> None:
        """Test helper to add entry to hass."""
        hass.config_entries._entries[self.entry_id] = self

    def add_to_manager(self, manager: config_entries.ConfigEntries) -> None:
        """Test helper to add entry to entry manager."""
        manager._entries[self.entry_id] = self

    def mock_state(
        self,
        hass: HomeAssistant,
        state: config_entries.ConfigEntryState,
        reason: str | None = None,
    ) -> None:
        """Mock the state of a config entry to be used in tests.

        Currently this is a wrapper around _async_set_state, but it may
        change in the future.

        It is preferable to get the config entry into the desired state
        by using the normal config entry methods, and this helper
        is only intended to be used in cases where that is not possible.

        When in doubt, this helper should not be used in new code
        and is only intended for backwards compatibility with existing
        tests.
        """
        self._async_set_state(hass, state, reason)

    async def start_reauth_flow(
        self,
        hass: HomeAssistant,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Start a reauthentication flow."""
        if self.entry_id not in hass.config_entries._entries:
            raise ValueError("Config entry must be added to hass to start reauth flow")
        return await start_reauth_flow(hass, self, context, data)

    async def start_reconfigure_flow(
        self,
        hass: HomeAssistant,
        *,
        show_advanced_options: bool = False,
    ) -> ConfigFlowResult:
        """Start a reconfiguration flow."""
        if self.entry_id not in hass.config_entries._entries:
            raise ValueError(
                "Config entry must be added to hass to start reconfiguration flow"
            )
        return await hass.config_entries.flow.async_init(
            self.domain,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": self.entry_id,
                "show_advanced_options": show_advanced_options,
            },
        )

    async def start_subentry_reconfigure_flow(
        self,
        hass: HomeAssistant,
        subentry_flow_type: str,
        subentry_id: str,
        *,
        show_advanced_options: bool = False,
    ) -> ConfigFlowResult:
        """Start a subentry reconfiguration flow."""
        if self.entry_id not in hass.config_entries._entries:
            raise ValueError(
                "Config entry must be added to hass to start reconfiguration flow"
            )
        return await hass.config_entries.subentries.async_init(
            (self.entry_id, subentry_flow_type),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry_id,
                "show_advanced_options": show_advanced_options,
            },
        )


async def start_reauth_flow(
    hass: HomeAssistant,
    entry: ConfigEntry,
    context: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
) -> ConfigFlowResult:
    """Start a reauthentication flow for a config entry.

    This helper method should be aligned with `ConfigEntry._async_init_reauth`.
    """
    return await hass.config_entries.flow.async_init(
        entry.domain,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "title_placeholders": {"name": entry.title},
            "unique_id": entry.unique_id,
        }
        | (context or {}),
        data=entry.data | (data or {}),
    )


def patch_yaml_files(files_dict, endswith=True):
    """Patch load_yaml with a dictionary of yaml files."""
    # match using endswith, start search with longest string
    matchlist = sorted(files_dict.keys(), key=len) if endswith else []

    def mock_open_f(fname, **_):
        """Mock open() in the yaml module, used by load_yaml."""
        # Return the mocked file on full match
        if isinstance(fname, pathlib.Path):
            fname = str(fname)

        if fname in files_dict:
            _LOGGER.debug("patch_yaml_files match %s", fname)
            res = StringIO(files_dict[fname])
            setattr(res, "name", fname)
            return res

        # Match using endswith
        for ends in matchlist:
            if fname.endswith(ends):
                _LOGGER.debug("patch_yaml_files end match %s: %s", ends, fname)
                res = StringIO(files_dict[ends])
                setattr(res, "name", fname)
                return res

        # Fallback for hass.components (i.e. services.yaml)
        if "homeassistant/components" in fname:
            _LOGGER.debug("patch_yaml_files using real file: %s", fname)
            return open(fname, encoding="utf-8")

        # Not found
        raise FileNotFoundError(f"File not found: {fname}")

    return patch.object(yaml_loader, "open", mock_open_f, create=True)


@contextmanager
def assert_setup_component(count, domain=None):
    """Collect valid configuration from setup_component.

    - count: The amount of valid platforms that should be setup
    - domain: The domain to count is optional. It can be automatically
              determined most of the time

    Use as a context manager around setup.setup_component
        with assert_setup_component(0) as result_config:
            setup_component(hass, domain, start_config)
            # using result_config is optional
    """
    config = {}

    async def mock_psc(
        hass: HomeAssistant,
        config_input: ConfigType,
        integration: loader.Integration,
        component: loader.ComponentProtocol | None = None,
    ) -> IntegrationConfigInfo:
        """Mock the prepare_setup_component to capture config."""
        domain_input = integration.domain
        integration_config_info = await async_process_component_config(
            hass, config_input, integration, component
        )
        res = integration_config_info.config
        config[domain_input] = None if res is None else res.get(domain_input)
        _LOGGER.debug(
            "Configuration for %s, Validated: %s, Original %s",
            domain_input,
            config[domain_input],
            config_input.get(domain_input),
        )
        return integration_config_info

    assert isinstance(config, dict)
    with patch("homeassistant.config.async_process_component_config", mock_psc):
        yield config

    if domain is None:
        assert len(config) == 1, (
            f"assert_setup_component requires DOMAIN: {list(config.keys())}"
        )
        domain = list(config.keys())[0]

    res = config.get(domain)
    res_len = 0 if res is None else len(res)
    assert res_len == count, (
        f"setup_component failed, expected {count} got {res_len}: {res}"
    )


def mock_restore_cache(hass: HomeAssistant, states: Sequence[State]) -> None:
    """Mock the DATA_RESTORE_CACHE."""
    key = rs.DATA_RESTORE_STATE
    data = rs.RestoreStateData(hass)
    now = dt_util.utcnow()

    last_states = {}
    for state in states:
        restored_state = state.as_dict()
        restored_state = {
            **restored_state,
            "attributes": json.loads(
                json.dumps(restored_state["attributes"], cls=JSONEncoder)
            ),
        }
        last_states[state.entity_id] = rs.StoredState.from_dict(
            {"state": restored_state, "last_seen": now}
        )
    data.last_states = last_states
    _LOGGER.debug("Restore cache: %s", data.last_states)
    assert len(data.last_states) == len(states), f"Duplicate entity_id? {states}"

    rs.async_get.cache_clear()
    hass.data[key] = data


def mock_restore_cache_with_extra_data(
    hass: HomeAssistant, states: Sequence[tuple[State, Mapping[str, Any]]]
) -> None:
    """Mock the DATA_RESTORE_CACHE."""
    key = rs.DATA_RESTORE_STATE
    data = rs.RestoreStateData(hass)
    now = dt_util.utcnow()

    last_states = {}
    for state, extra_data in states:
        restored_state = state.as_dict()
        restored_state = {
            **restored_state,
            "attributes": json.loads(
                json.dumps(restored_state["attributes"], cls=JSONEncoder)
            ),
        }
        last_states[state.entity_id] = rs.StoredState.from_dict(
            {"state": restored_state, "extra_data": extra_data, "last_seen": now}
        )
    data.last_states = last_states
    _LOGGER.debug("Restore cache: %s", data.last_states)
    assert len(data.last_states) == len(states), f"Duplicate entity_id? {states}"

    rs.async_get.cache_clear()
    hass.data[key] = data


async def async_mock_restore_state_shutdown_restart(
    hass: HomeAssistant,
) -> rs.RestoreStateData:
    """Mock shutting down and saving restore state and restoring."""
    data = rs.async_get(hass)
    await data.async_dump_states()
    await async_mock_load_restore_state_from_storage(hass)
    return data


async def async_mock_load_restore_state_from_storage(
    hass: HomeAssistant,
) -> None:
    """Mock loading restore state from storage.

    hass_storage must already be mocked.
    """
    await rs.async_get(hass).async_load()


class MockEntity(entity.Entity):
    """Mock Entity class."""

    def __init__(self, **values: Any) -> None:
        """Initialize an entity."""
        self._values = values

        if "entity_id" in values:
            self.entity_id = values["entity_id"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._handle("available")

    @property
    def capability_attributes(self) -> Mapping[str, Any] | None:
        """Info about capabilities."""
        return self._handle("capability_attributes")

    @property
    def device_class(self) -> str | None:
        """Info how device should be classified."""
        return self._handle("device_class")

    @property
    def device_info(self) -> dr.DeviceInfo | None:
        """Info how it links to a device."""
        return self._handle("device_info")

    @property
    def entity_category(self) -> entity.EntityCategory | None:
        """Return the entity category."""
        return self._handle("entity_category")

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        return self._handle("extra_state_attributes")

    @property
    def has_entity_name(self) -> bool:
        """Return the has_entity_name name flag."""
        return self._handle("has_entity_name")

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._handle("entity_registry_enabled_default")

    @property
    def entity_registry_visible_default(self) -> bool:
        """Return if the entity should be visible when first added to the entity registry."""
        return self._handle("entity_registry_visible_default")

    @property
    def icon(self) -> str | None:
        """Return the suggested icon."""
        return self._handle("icon")

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._handle("name")

    @property
    def should_poll(self) -> bool:
        """Return the ste of the polling."""
        return self._handle("should_poll")

    @property
    def supported_features(self) -> int | None:
        """Info about supported features."""
        return self._handle("supported_features")

    @property
    def translation_key(self) -> str | None:
        """Return the translation key."""
        return self._handle("translation_key")

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self._handle("unique_id")

    @property
    def unit_of_measurement(self) -> str | None:
        """Info on the units the entity state is in."""
        return self._handle("unit_of_measurement")

    def _handle(self, attr: str) -> Any:
        """Return attribute value."""
        if attr in self._values:
            return self._values[attr]
        return getattr(super(), attr)


@contextmanager
def mock_storage(data: dict[str, Any] | None = None) -> Generator[dict[str, Any]]:
    """Mock storage.

    Data is a dict {'key': {'version': version, 'data': data}}

    Written data will be converted to JSON to ensure JSON parsing works.
    """
    if data is None:
        data = {}

    orig_load = storage.Store._async_load

    async def mock_async_load(
        store: storage.Store,
    ) -> dict[str, Any] | list[Any] | None:
        """Mock version of load."""
        if store._data is None:
            # No data to load
            if store.key not in data:
                # Make sure the next attempt will still load
                store._load_task = None
                return None

            mock_data = data.get(store.key)

            if "data" not in mock_data or "version" not in mock_data:
                _LOGGER.error('Mock data needs "version" and "data"')
                raise ValueError('Mock data needs "version" and "data"')

            store._data = mock_data

        # Route through original load so that we trigger migration
        loaded = await orig_load(store)
        _LOGGER.debug("Loading data for %s: %s", store.key, loaded)
        return loaded

    async def mock_write_data(
        store: storage.Store, path: str, data_to_write: dict[str, Any]
    ) -> None:
        """Mock version of write data."""
        # To ensure that the data can be serialized
        _LOGGER.debug("Writing data to %s: %s", store.key, data_to_write)
        raise_contains_mocks(data_to_write)

        if "data_func" in data_to_write:
            data_to_write["data"] = data_to_write.pop("data_func")()

        encoder = store._encoder
        if encoder and encoder is not JSONEncoder:
            # If they pass a custom encoder that is not the
            # default JSONEncoder, we use the slow path of json.dumps
            dump = ft.partial(json.dumps, cls=store._encoder)
        else:
            dump = _orjson_default_encoder
        data[store.key] = json_loads(dump(data_to_write))

    async def mock_remove(store: storage.Store) -> None:
        """Remove data."""
        data.pop(store.key, None)

    with (
        patch(
            "homeassistant.helpers.storage.Store._async_load",
            side_effect=mock_async_load,
            autospec=True,
        ),
        patch(
            "homeassistant.helpers.storage.Store._async_write_data",
            side_effect=mock_write_data,
            autospec=True,
        ),
        patch(
            "homeassistant.helpers.storage.Store.async_remove",
            side_effect=mock_remove,
            autospec=True,
        ),
    ):
        yield data


async def flush_store(store: storage.Store) -> None:
    """Make sure all delayed writes of a store are written."""
    if store._data is None:
        return

    store._async_cleanup_final_write_listener()
    store._async_cleanup_delay_listener()
    await store._async_handle_write_data()


async def get_system_health_info(hass: HomeAssistant, domain: str) -> dict[str, Any]:
    """Get system health info."""
    return await hass.data["system_health"][domain].info_callback(hass)


@contextmanager
def mock_config_flow(domain: str, config_flow: type[ConfigFlow]) -> Iterator[None]:
    """Mock a config flow handler."""
    original_handler = config_entries.HANDLERS.get(domain)
    config_entries.HANDLERS[domain] = config_flow
    _LOGGER.info("Adding mock config flow: %s", domain)
    yield
    config_entries.HANDLERS.pop(domain)
    if original_handler:
        config_entries.HANDLERS[domain] = original_handler


def mock_integration(
    hass: HomeAssistant,
    module: MockModule,
    built_in: bool = True,
    top_level_files: set[str] | None = None,
) -> loader.Integration:
    """Mock an integration."""
    integration = loader.Integration(
        hass,
        f"{loader.PACKAGE_BUILTIN}.{module.DOMAIN}"
        if built_in
        else f"{loader.PACKAGE_CUSTOM_COMPONENTS}.{module.DOMAIN}",
        pathlib.Path(""),
        module.mock_manifest(),
        top_level_files,
    )

    def mock_import_platform(platform_name: str) -> NoReturn:
        raise ImportError(
            f"Mocked unable to import platform '{integration.pkg_path}.{platform_name}'",
            name=f"{integration.pkg_path}.{platform_name}",
        )

    integration._import_platform = mock_import_platform

    _LOGGER.info("Adding mock integration: %s", module.DOMAIN)
    integration_cache = hass.data[loader.DATA_INTEGRATIONS]
    integration_cache[module.DOMAIN] = integration

    module_cache = hass.data[loader.DATA_COMPONENTS]
    module_cache[module.DOMAIN] = module

    return integration


def mock_platform(
    hass: HomeAssistant,
    platform_path: str,
    module: Mock | MockPlatform | None = None,
    built_in=True,
) -> None:
    """Mock a platform.

    platform_path is in form hue.config_flow.
    """
    domain, _, platform_name = platform_path.partition(".")
    integration_cache = hass.data[loader.DATA_INTEGRATIONS]
    module_cache = hass.data[loader.DATA_COMPONENTS]

    if domain not in integration_cache:
        mock_integration(hass, MockModule(domain), built_in=built_in)

    integration_cache[domain]._top_level_files.add(f"{platform_name}.py")
    _LOGGER.info("Adding mock integration platform: %s", platform_path)
    module_cache[platform_path] = module or Mock()


def async_capture_events[_DataT: Mapping[str, Any] = dict[str, Any]](
    hass: HomeAssistant, event_name: EventType[_DataT] | str
) -> list[Event[_DataT]]:
    """Create a helper that captures events."""
    events: list[Event[_DataT]] = []

    @callback
    def capture_events(event: Event[_DataT]) -> None:
        events.append(event)

    hass.bus.async_listen(event_name, capture_events)

    return events


@callback
def async_mock_signal[*_Ts](
    hass: HomeAssistant, signal: SignalType[*_Ts] | str
) -> list[tuple[*_Ts]]:
    """Catch all dispatches to a signal."""
    calls: list[tuple[*_Ts]] = []

    @callback
    def mock_signal_handler(*args: *_Ts) -> None:
        """Mock service call."""
        calls.append(args)

    async_dispatcher_connect(hass, signal, mock_signal_handler)

    return calls


_SENTINEL = object()


class _HA_ANY:
    """A helper object that compares equal to everything.

    Based on unittest.mock.ANY, but modified to not show up in pytest's equality
    assertion diffs.
    """

    _other = _SENTINEL

    def __eq__(self, other: object) -> bool:
        """Test equal."""
        self._other = other
        return True

    def __ne__(self, other: object) -> bool:
        """Test not equal."""
        self._other = other
        return False

    def __repr__(self) -> str:
        """Return repr() other to not show up in pytest quality diffs."""
        if self._other is _SENTINEL:
            return "<ANY>"
        return repr(self._other)


ANY = _HA_ANY()


def raise_contains_mocks(val: Any) -> None:
    """Raise for mocks."""
    if isinstance(val, Mock):
        raise TypeError(val)

    if isinstance(val, dict):
        for dict_value in val.values():
            raise_contains_mocks(dict_value)

    if isinstance(val, list):
        for dict_value in val:
            raise_contains_mocks(dict_value)


@callback
def async_get_persistent_notifications(
    hass: HomeAssistant,
) -> dict[str, pn.Notification]:
    """Get the current persistent notifications."""
    return pn._async_get_or_create_notifications(hass)


def async_mock_cloud_connection_status(hass: HomeAssistant, connected: bool) -> None:
    """Mock a signal the cloud disconnected."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.cloud import (
        SIGNAL_CLOUD_CONNECTION_STATE,
        CloudConnectionState,
    )

    if connected:
        state = CloudConnectionState.CLOUD_CONNECTED
    else:
        state = CloudConnectionState.CLOUD_DISCONNECTED
    async_dispatcher_send(hass, SIGNAL_CLOUD_CONNECTION_STATE, state)


@asynccontextmanager
async def async_call_logger_set_level(
    logger: str,
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "FATAL", "CRITICAL"],
    *,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> AsyncGenerator[None]:
    """Context manager to reset loggers after logger.set_level call."""
    assert LOGGER_DOMAIN in hass.data, "'logger' integration not setup"
    with caplog.at_level(logging.NOTSET, logger):
        await hass.services.async_call(
            LOGGER_DOMAIN,
            SERVICE_SET_LEVEL,
            {logger: level},
            blocking=True,
        )
        await hass.async_block_till_done()
        yield
        _clear_logger_overwrites(hass)


def import_and_test_deprecated_constant_enum(
    caplog: pytest.LogCaptureFixture,
    module: ModuleType,
    replacement: Enum,
    constant_prefix: str,
    breaks_in_ha_version: str,
) -> None:
    """Import and test deprecated constant replaced by a enum.

    - Import deprecated enum
    - Assert value is the same as the replacement
    - Assert a warning is logged
    - Assert the deprecated constant is included in the modules.__dir__()
    - Assert the deprecated constant is included in the modules.__all__()
    """
    import_and_test_deprecated_constant(
        caplog,
        module,
        constant_prefix + replacement.name,
        f"{replacement.__class__.__name__}.{replacement.name}",
        replacement,
        breaks_in_ha_version,
    )


def import_and_test_deprecated_constant(
    caplog: pytest.LogCaptureFixture,
    module: ModuleType,
    constant_name: str,
    replacement_name: str,
    replacement: Any,
    breaks_in_ha_version: str,
) -> None:
    """Import and test deprecated constant replaced by a value.

    - Import deprecated constant
    - Assert value is the same as the replacement
    - Assert a warning is logged
    - Assert the deprecated constant is included in the modules.__dir__()
    - Assert the deprecated constant is included in the modules.__all__()
    """
    value = import_deprecated_constant(module, constant_name)
    assert value == replacement
    assert (
        module.__name__,
        logging.WARNING,
        (
            f"{constant_name} was used from test_constant_deprecation,"
            f" this is a deprecated constant which will be removed in HA Core {breaks_in_ha_version}. "
            f"Use {replacement_name} instead, please report "
            "it to the author of the 'test_constant_deprecation' custom integration"
        ),
    ) in caplog.record_tuples

    # verify deprecated constant is included in dir()
    assert constant_name in dir(module)
    assert constant_name in module.__all__


def import_and_test_deprecated_alias(
    caplog: pytest.LogCaptureFixture,
    module: ModuleType,
    alias_name: str,
    replacement: Any,
    breaks_in_ha_version: str,
) -> None:
    """Import and test deprecated alias replaced by a value.

    - Import deprecated alias
    - Assert value is the same as the replacement
    - Assert a warning is logged
    - Assert the deprecated alias is included in the modules.__dir__()
    - Assert the deprecated alias is included in the modules.__all__()
    """
    replacement_name = f"{replacement.__module__}.{replacement.__name__}"
    value = import_deprecated_constant(module, alias_name)
    assert value == replacement
    assert (
        module.__name__,
        logging.WARNING,
        (
            f"{alias_name} was used from test_constant_deprecation,"
            f" this is a deprecated alias which will be removed in HA Core {breaks_in_ha_version}. "
            f"Use {replacement_name} instead, please report "
            "it to the author of the 'test_constant_deprecation' custom integration"
        ),
    ) in caplog.record_tuples

    # verify deprecated alias is included in dir()
    assert alias_name in dir(module)
    assert alias_name in module.__all__


def help_test_all(module: ModuleType) -> None:
    """Test module.__all__ is correctly set."""
    assert set(module.__all__) == {
        itm for itm in dir(module) if not itm.startswith("_")
    }


def extract_stack_to_frame(extract_stack: list[Mock]) -> FrameType:
    """Convert an extract stack to a frame list."""
    stack = list(extract_stack)
    _globals = globals()
    for frame in stack:
        frame.f_back = None
        frame.f_globals = _globals
        frame.f_code.co_filename = frame.filename
        frame.f_lineno = int(frame.lineno)

    top_frame = stack.pop()
    current_frame = top_frame
    while stack and (next_frame := stack.pop()):
        current_frame.f_back = next_frame
        current_frame = next_frame

    return top_frame


def setup_test_component_platform(
    hass: HomeAssistant,
    domain: str,
    entities: Iterable[Entity],
    from_config_entry: bool = False,
    built_in: bool = True,
) -> MockPlatform:
    """Mock a test component platform for tests."""

    async def _async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up a test component platform."""
        async_add_entities(entities)

    platform = MockPlatform(
        async_setup_platform=_async_setup_platform,
    )

    # avoid creating config entry setup if not needed
    if from_config_entry:

        async def _async_setup_entry(
            hass: HomeAssistant,
            entry: ConfigEntry,
            async_add_entities: AddConfigEntryEntitiesCallback,
        ) -> None:
            """Set up a test component platform."""
            async_add_entities(entities)

        platform.async_setup_entry = _async_setup_entry
        platform.async_setup_platform = None

    mock_platform(hass, f"test.{domain}", platform, built_in=built_in)
    return platform


async def snapshot_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry_id: str,
) -> None:
    """Snapshot a platform."""
    entity_entries = er.async_entries_for_config_entry(entity_registry, config_entry_id)
    assert entity_entries
    assert len({entity_entry.domain for entity_entry in entity_entries}) == 1, (
        "Please limit the loaded platforms to 1 platform."
    )
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_entry.disabled_by is None, "Please enable all entities."
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


@lru_cache
def get_quality_scale(integration: str) -> dict[str, QualityScaleStatus]:
    """Load quality scale for integration."""
    quality_scale_file = pathlib.Path(
        f"homeassistant/components/{integration}/quality_scale.yaml"
    )
    if not quality_scale_file.exists():
        return {}
    raw = load_yaml_dict(quality_scale_file)
    return {
        rule: (
            QualityScaleStatus(details)
            if isinstance(details, str)
            else QualityScaleStatus(details["status"])
        )
        for rule, details in raw["rules"].items()
    }


def get_schema_suggested_value(schema: vol.Schema, key: str) -> Any | None:
    """Get suggested value for key in voluptuous schema."""
    for schema_key in schema:
        if schema_key == key:
            if (
                schema_key.description is None
                or "suggested_value" not in schema_key.description
            ):
                return None
            return schema_key.description["suggested_value"]
    return None


class MockDhcpServiceInfo(DhcpServiceInfo):
    """Mocked DHCP service info."""

    def __init__(self, ip: str, hostname: str, macaddress: str) -> None:
        """Initialize the mock service info."""
        # Historically, the MAC address was formatted without colons
        # and since all consumers of this data are expecting it to be
        # formatted without colons we will continue to do so
        super().__init__(
            ip=ip,
            hostname=hostname,
            macaddress=dr.format_mac(macaddress).replace(":", ""),
        )

    async def start_discovery_flow(
        self, hass: HomeAssistant, domain: str
    ) -> ConfigFlowResult:
        """Start a reauthentication flow."""
        return await hass.config_entries.flow.async_init(
            domain, context={"source": config_entries.SOURCE_DHCP}, data=self
        )
