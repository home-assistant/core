"""Tests for the powersensor Home Assistant  config_flow.

This module includes various unit tests to ensure that the configuration flow for
the power sensor component works correctly.
"""

import asyncio
from ipaddress import ip_address
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
import homeassistant.components.powersensor
from homeassistant.components.powersensor import PowersensorConfigFlow
from homeassistant.components.powersensor.config_flow import get_sensor_display_name
from homeassistant.components.powersensor.const import (
    DOMAIN,
    ROLE_UNKNOWN,
    ROLE_UPDATE_SIGNAL,
    ROLE_WATER,
)
from homeassistant.components.powersensor.sensor import PowersensorRuntimeData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

MAC = "a4cf1218f158"
SECOND_MAC = "a4cf1218f160"


@pytest.fixture(autouse=True)
def bypass_setup(monkeypatch: pytest.MonkeyPatch):
    """A pytest fixture to bypass the actual setup of the powersensor component during tests.

    It replaces the async_setup_entry method with a mock that returns True.
    """
    monkeypatch.setattr(
        homeassistant.components.powersensor,
        "async_setup_entry",
        AsyncMock(return_value=True),
    )


def validate_config_data(data):
    """Validates the configuration data received from the powersensor config flow.

    Args:
        data (dict): The configuration data to be validated.

    Raises:
        AssertionError: If the configuration data does not meet the expected format.
    """
    assert isinstance(data["devices"], dict)
    assert isinstance(data["roles"], dict)


### Tests ################################################


async def test_user(hass: HomeAssistant) -> None:
    """Tests the user-initiated configuration flow for the powersensor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": result["step_id"]},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    validate_config_data(result["data"])


async def test_zeroconf(hass: HomeAssistant) -> None:
    """Tests the zeroconf-initiated configuration flow for the powersensor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.33"),
            ip_addresses=[ip_address("192.168.0.33")],
            hostname=f"Powersensor-gateway-{MAC}-civet.local",
            name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={
                "version": "1",
                "id": f"{MAC}",
            },
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": result["step_id"]},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    validate_config_data(result["data"])
    assert MAC in result["data"]["devices"]


async def test_zeroconf_two_plugs(hass: HomeAssistant) -> None:
    """This test ensures that the configuration flow correctly handles the discovery of two Powersensor plugs via Zeroconf, with subsequent discoveries being aborted if the integration is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.33"),
            ip_addresses=[ip_address("192.168.0.33")],
            hostname=f"Powersensor-gateway-{MAC}-civet.local",
            name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={
                "version": "1",
                "id": f"{MAC}",
            },
        ),
    )

    second_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.37"),
            ip_addresses=[ip_address("192.168.0.37")],
            hostname=f"Powersensor-gateway-{SECOND_MAC}-civet.local",
            name=f"Powersensor-gateway-{SECOND_MAC}-civet._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={
                "version": "1",
                "id": f"{SECOND_MAC}",
            },
        ),
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": result["step_id"]},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    validate_config_data(result["data"])
    assert MAC in result["data"]["devices"]

    # # we expect the second plug config flow to get canceled if the integration has already been configured
    assert second_result["type"] == FlowResultType.ABORT


async def test_zeroconf_two_plugs_race(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate a race condition where two PowerSensor devices are discovered simultaneously, testing that the second device gets cancelled and the first one completes the config flow."""

    # WIP: this may not yet really simulate the race condition previously observed in HA
    call_count = 0
    original_set_unique_id = PowersensorConfigFlow.async_set_unique_id

    async def delayed_set_unique_id(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(1.0)
        return await original_set_unique_id(self, *args, **kwargs)

    monkeypatch.setattr(
        PowersensorConfigFlow, "async_set_unique_id", delayed_set_unique_id
    )
    task1 = asyncio.create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZeroconfServiceInfo(
                ip_address=ip_address("192.168.0.33"),
                ip_addresses=[ip_address("192.168.0.33")],
                hostname=f"Powersensor-gateway-{MAC}-civet.local",
                name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local",
                port=49476,
                type="_powersensor._udp.local.",
                properties={
                    "version": "1",
                    "id": f"{MAC}",
                },
            ),
        )
    )
    await asyncio.sleep(0.99)
    task2 = asyncio.create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=ZeroconfServiceInfo(
                ip_address=ip_address("192.168.0.37"),
                ip_addresses=[ip_address("192.168.0.37")],
                hostname=f"Powersensor-gateway-{SECOND_MAC}-civet.local",
                name=f"Powersensor-gateway-{SECOND_MAC}-civet._powersensor._udp.local",
                port=49476,
                type="_powersensor._udp.local.",
                properties={
                    "version": "1",
                    "id": f"{SECOND_MAC}",
                },
            ),
        )
    )
    result, second_result = await asyncio.gather(task1, task2)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # # # we expect the plug arriving second in config flow to get canceled if the integration has already been configured
    assert second_result["type"] == FlowResultType.ABORT

    second_result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": result["step_id"]},
    )
    assert second_result["type"] == FlowResultType.CREATE_ENTRY
    validate_config_data(second_result["data"])
    assert MAC in second_result["data"]["devices"]


async def test_zeroconf_two_plugs_simultaneous_discovery(
    hass: HomeAssistant,
) -> None:
    """Test that simultaneous zeroconf discoveries only produce one config flow.

    When two plugs are discovered at the same time, each triggers a zeroconf
    flow. The first flow should proceed to the confirmation step; the second
    should abort immediately with 'already_in_progress' because
    _async_prepare_setup() detects the first flow is already running.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.33"),
            ip_addresses=[ip_address("192.168.0.33")],
            hostname=f"Powersensor-gateway-{MAC}-civet.local",
            name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={
                "version": "1",
                "id": f"{MAC}",
            },
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Second plug discovered simultaneously — should abort, not start another flow.
    second_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.37"),
            ip_addresses=[ip_address("192.168.0.37")],
            hostname=f"Powersensor-gateway-{SECOND_MAC}-civet.local",
            name=f"Powersensor-gateway-{SECOND_MAC}-civet._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={
                "version": "1",
                "id": f"{SECOND_MAC}",
            },
        ),
    )
    assert second_result["type"] == FlowResultType.ABORT
    assert second_result["reason"] == "already_in_progress"

    # Complete the first flow normally.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": result["step_id"]},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    validate_config_data(result["data"])

    assert second_result["type"] == FlowResultType.ABORT


async def test_zeroconf_already_discovered(hass: HomeAssistant) -> None:
    """Test behavior when trying to discover and configure a PowerSensor device that has already been discovered.

    This test checks that:
    - The first discovery attempt completes the config flow.
    - A second discovery attempt from the same IP address is aborted with the 'already_in_progress' reason.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.33"),
            ip_addresses=[ip_address("192.168.0.33")],
            hostname=f"Powersensor-gateway-{MAC}-civet.local",
            name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={
                "version": "1",
                "id": f"{MAC}",
            },
        ),
    )

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.33"),
            ip_addresses=[ip_address("192.168.0.33")],
            hostname=f"Powersensor-gateway-{MAC}-civet.local",
            name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={
                "version": "1",
                "id": f"{MAC}",
            },
        ),
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": result["step_id"]},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    validate_config_data(result["data"])
    assert MAC in result["data"]["devices"]


async def test_zeroconf_missing_id(hass: HomeAssistant) -> None:
    """No plug should advertise without an 'id' property, but just in case..."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.0.33"),
            ip_addresses=[ip_address("192.168.0.33")],
            hostname=f"Powersensor-gateway-{MAC}-civet.local",
            name=f"Powersensor-gateway-{MAC}-civet._powersensor._udp.local",
            port=49476,
            type="_powersensor._udp.local.",
            properties={
                "version": "1",
            },
        ),
    )
    assert result["type"] == FlowResultType.ABORT


@pytest.mark.parametrize("check_translations", [None])
async def test_reconfigure(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, def_config_entry
) -> None:
    """Validates the device reconfiguration flow and role updates."""

    # Make the config_flow use our precanned entry
    def my_entry(_):
        return def_config_entry

    monkeypatch.setattr(hass.config_entries, "async_get_entry", my_entry)

    # Patch async_update_entry so it doesn't require the entry to be registered
    updated_data: dict = {}

    def capture_update(entry, *, data=None, **_kwargs):
        if data is not None:
            updated_data.update(data)
        return True

    monkeypatch.setattr(hass.config_entries, "async_update_entry", capture_update)
    # Kick off the reconfigure
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": def_config_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM

    # Hook into role updates to see role change come through
    called = 0

    async def verify_roles(mac, role):
        nonlocal called
        called += 1
        assert mac == "cafebabe" and role == "water"

    discon = async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, verify_roles)

    # Prepare user_input, and submit it
    mac2name = {
        mac: get_sensor_display_name(def_config_entry, mac)
        for mac in def_config_entry.runtime_data.dispatcher.sensors
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={mac2name["cafebabe"]: "water"}
    )
    discon()
    # Verify
    assert result["type"] == FlowResultType.ABORT
    assert called == 1


@pytest.mark.parametrize("check_translations", [None])
async def test_unknown_role(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, def_config_entry
) -> None:
    """Tests the system's response to unknown roles during configuration step."""

    # Make the config_flow use our pre-canned entry
    def my_entry(_):
        return def_config_entry

    monkeypatch.setattr(hass.config_entries, "async_get_entry", my_entry)

    # Patch async_update_entry so it doesn't require the entry to be registered
    def capture_update(entry, *, data=None, **_kwargs):
        return True

    monkeypatch.setattr(hass.config_entries, "async_update_entry", capture_update)

    # Kick off the reconfigure
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": def_config_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM

    # Hook into role updates to see role change come through
    called = 0

    async def verify_roles(mac, role):
        nonlocal called
        called += 1
        assert mac == "d3adB33f" and role is None

    discon = async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, verify_roles)

    # Prepare user_input, and submit it
    mac2name = {
        mac: get_sensor_display_name(def_config_entry, mac)
        for mac in def_config_entry.runtime_data.dispatcher.sensors
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={mac2name["d3adB33f"]: ROLE_UNKNOWN}
    )
    discon()
    # Verify
    assert result["type"] == FlowResultType.ABORT
    assert called == 1


async def test_abort_due_to_missing_runtime_data(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, def_config_entry
) -> None:
    """Tests the system's response to missing runtime data during the configuration step."""
    del def_config_entry.runtime_data

    # Make the config_flow use our pre-canned entry
    def my_entry(_):
        return def_config_entry

    monkeypatch.setattr(hass.config_entries, "async_get_entry", my_entry)

    # Kick off the reconfigure
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": def_config_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.ABORT


async def test_abort_due_to_missing_dispatcher(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, def_config_entry
) -> None:
    """Tests the system's response to missing dispatcher in the runtime data during the configuration step."""
    _old_rd = def_config_entry.runtime_data
    def_config_entry.runtime_data = PowersensorRuntimeData(
        vhh=_old_rd.vhh,
        dispatcher=None,
        zeroconf=None,
    )

    # Make the config_flow use our pre-canned entry
    def my_entry(_):
        return def_config_entry

    monkeypatch.setattr(hass.config_entries, "async_get_entry", my_entry)

    # Kick off the reconfigure
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": def_config_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.ABORT


async def test_user_already_configured(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a second user-initiated flow aborts when an entry already exists.

    The integration uses single_config_entry + _abort_if_unique_id_configured()
    as its duplicate guard. The flow should abort with 'already_configured' when
    a config entry with the same unique ID (DOMAIN) already exists.
    """
    # Complete a first flow so an entry exists.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": result["step_id"]},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # A second user flow should now abort because the unique ID is taken.
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "single_instance_allowed"


@pytest.mark.parametrize("check_translations", [None])
async def test_reconfigure_sensor_disappears_between_form_and_submit(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, def_config_entry
) -> None:
    """Test that a sensor that disappears between form render and submit is skipped.

    Lines 103-105 of config_flow.py: mac2name is rebuilt on every call to
    async_step_reconfigure. If dispatcher.sensors shrinks between the first
    call (form render) and the second call (form submit), a name that was a
    valid schema key on the first call will be absent from name2mac on the
    second, so name2mac.get() returns None and the guard is hit.
    """
    monkeypatch.setattr(
        hass.config_entries, "async_get_entry", lambda _: def_config_entry
    )
    monkeypatch.setattr(
        hass.config_entries, "async_update_entry", lambda *a, **kw: True
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": def_config_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM

    # cafebabe was present when the form was rendered — schema accepts its name.
    # Now remove it so mac2name on the second call won't contain it,
    # causing name2mac.get() to return None for it.
    mac2name = {
        mac: get_sensor_display_name(def_config_entry, mac)
        for mac in def_config_entry.runtime_data.dispatcher.sensors
    }
    def_config_entry.runtime_data.dispatcher.sensors = {
        "c001eat5": "house-net",
        "d3adB33f": None,
    }

    signal_fired = []

    async def capture_role(mac, role):
        signal_fired.append(mac)

    discon = async_dispatcher_connect(hass, ROLE_UPDATE_SIGNAL, capture_role)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={mac2name["cafebabe"]: ROLE_WATER},
    )
    discon()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "roles_applied"
    # cafebabe disappeared — its name hit the None guard, no signal fired
    assert signal_fired == []


async def test_user_flow_aborts_when_already_in_progress(hass: HomeAssistant) -> None:
    """Test that a user flow aborts if another flow is already in progress.

    Line 171 of config_flow.py: _async_prepare_setup returns an abort result
    when _async_in_progress() is True.  async_step_user returns that result
    directly.  This is triggered by starting a second user flow while the
    first is still sitting on the confirm form.
    """
    # Start a first user flow and leave it on the confirm form
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM

    # Start a second user flow — _async_in_progress() is now True
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"
