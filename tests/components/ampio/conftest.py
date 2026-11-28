"""Fixtures for the Ampio integration tests.

The library client is mocked at the integration boundary and seeded with
real ``ampio_mqtt`` model instances, so tests drive the integration through
the same public surface the library exposes: the state properties and the
``subscribe`` event stream (dispatched via :func:`emit`).
"""

from collections.abc import Generator
from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock, patch

from ampio_mqtt import AmpioObject, AmpioServerInfo, parse_module_address
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ampio.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

MSERV_MAC = "47846"
MSENS_MAC = 0xCB8F
MSENS_DEVICE_NAME = "Ampio module 0xCB8F"


def module_identifier(mac: int) -> tuple[str, str]:
    """The registry identifier of the module device on ``mac``."""
    return (DOMAIN, f"module:0x{mac:X}")


def object_unique_id(oid: int) -> str:
    """The unique id of the entity built from object ``oid``."""
    return f"obj_{oid}"


def object_identifier(oid: int) -> tuple[str, str]:
    """The registry identifier of the child device of object ``oid``."""
    return (DOMAIN, f"obj_{oid}")


MSENS_IDENTIFIER = module_identifier(MSENS_MAC)
MREL_MAC = 0xBE82

USER_INPUT = {
    CONF_HOST: "ampio.test",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}

# The identity reply of the default test server. An account created in the
# Ampio app carries a positive user id.
SERVER_INFO = AmpioServerInfo(
    mac=47846,
    user_id=2,
    server_version="1865",
    server_revision="409",
    mqtt_version="5.133.11",
    local_ip="10.0.0.1",
    device_id="0011223344556677",
)
# The reserved admin login carries user id -1.
ADMIN_SERVER_INFO = replace(SERVER_INFO, user_id=-1)


def make_object(
    oid: int,
    typ: str,
    interpretacja: int,
    *,
    leaf_id: str,
    funkcja: int = 1,
    name: str | None = None,
    state: str | None = None,
) -> AmpioObject:
    """Build a classified object the way discovery would."""
    return AmpioObject(
        id=oid,
        typ_komponentu=typ,
        name=name,
        interpretacja=interpretacja,
        funkcja=funkcja,
        address=parse_module_address(leaf_id),
        leaf_key=f"leaf_{leaf_id}",
        state=state,
    )


# The default object catalogue: one sensor per supported kind on the M-SENS
# at 0xCB8F, so the entity snapshot pins every description's device class,
# unit, precision, and display name.
DEFAULT_OBJECTS = (
    make_object(
        36,
        "temp",
        1,
        leaf_id="0_cb8f_76_0_1",
        name="Temperatura",
        state="24.4",
    ),
    make_object(
        37,
        "lin_wej",
        1,
        leaf_id="0_cb8f_74_0_2",
        funkcja=2,
        name="Wilgotność",
        state="42.000000",
    ),
    make_object(43, "lin_wej", 7, leaf_id="0_cb8f_74_0_3", funkcja=3, state="900.5"),
    make_object(44, "lin_wej", 2, leaf_id="0_cb8f_74_0_4", funkcja=5, state="1013.2"),
    make_object(45, "lin_wej", 6, leaf_id="0_cb8f_74_0_5", funkcja=6, state="1019.7"),
    make_object(46, "lin_wej", 3, leaf_id="0_cb8f_74_0_6", funkcja=7, state="38.5"),
    make_object(47, "lin_wej", 4, leaf_id="0_cb8f_74_0_7", funkcja=8, state="742"),
    make_object(48, "lin_wej", 5, leaf_id="0_cb8f_74_0_8", funkcja=9, state="23"),
)


def emit(client: MagicMock, event: Any) -> None:
    """Dispatch ``event`` to the live listeners subscribed on the mocked client.

    Iterates a snapshot: a listener whose dispatch triggers new
    subscriptions (a reload re-running setup) must not receive this event
    on its replacement registrations too.
    """
    for listener, of, object_id in list(client.live_subscriptions):
        if not isinstance(event, of):
            continue
        if object_id is not None and event.object.id != object_id:
            continue
        listener(event)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=USER_INPUT[CONF_HOST],
        data=USER_INPUT,
        unique_id=MSERV_MAC,
    )


@pytest.fixture
def mock_client_class() -> Generator[MagicMock]:
    """Patch AmpioClient in setup and in the config flow with one connected mock."""
    with (
        patch(
            "homeassistant.components.ampio.AmpioClient", autospec=True
        ) as client_class,
        patch(
            "homeassistant.components.ampio.config_flow.AmpioClient", new=client_class
        ),
    ):
        client_class.check_connection.return_value = SERVER_INFO
        client = client_class.return_value
        client.connect.return_value = True
        client.available = True
        client.objects = {obj.id: obj for obj in DEFAULT_OBJECTS}
        client.server_info = SERVER_INFO

        # Track live registrations so unsubscribing works: emit() must not
        # reach listeners from a torn-down setup. Unsubscribing is idempotent,
        # matching the real client's documented contract.
        subscriptions: list[tuple[Any, type | tuple[type, ...], int | None]] = []

        def subscribe(
            listener: Any,
            *,
            of: type | tuple[type, ...],
            object_id: int | None = None,
        ) -> Any:
            registration = (listener, of, object_id)
            subscriptions.append(registration)

            def unsubscribe() -> None:
                if registration in subscriptions:
                    subscriptions.remove(registration)

            return unsubscribe

        client.subscribe.side_effect = subscribe
        client.live_subscriptions = subscriptions
        yield client_class


@pytest.fixture
def mock_client(mock_client_class: MagicMock) -> MagicMock:
    """The mocked client instance the integration runs on."""
    return mock_client_class.return_value


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Patch the entry setup so config-flow tests don't run real setup."""
    with patch(
        "homeassistant.components.ampio.async_setup_entry", return_value=None
    ) as mock:
        yield mock
