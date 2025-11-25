"""Tests for Prana config flow."""

import pytest

from homeassistant.components.prana.config_flow import SERVICE_TYPE, ConfigFlow
from homeassistant.components.prana.const import CONF_CONFIG, CONF_MDNS
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant  # added
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_zeroconf_not_prana_device(hass: HomeAssistant) -> None:
    """Завершення, якщо знайдений пристрій не є Prana."""
    flow = ConfigFlow()
    flow.hass = hass

    info = ZeroconfServiceInfo(
        ip_address="192.168.1.10",
        ip_addresses=["192.168.1.10"],
        hostname="test.local",
        name="TestName._other._tcp.local.",
        type="_other._tcp.local.",
        port=1234,
        properties={},
    )

    result = await flow.async_step_zeroconf(info)
    assert result["type"] == "abort"
    assert result["reason"] == "not_prana_device"


@pytest.mark.asyncio
async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Якщо запис конфігурації вже є — discovery все ще переходить у confirm (немає already_configured)."""
    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain="prana",
        title="Test Prana",
        data={
            "name": "Test Prana",
            "host": "127.0.0.1",
            "config": {"some_key": "some_value"},
            "mdns": "_prana._tcp.local._test",
        },
        source="user",
        entry_id="123456",
        options={},
        discovery_keys=None,
        unique_id="_prana._tcp.local._test",
        subentries_data=None,
    )
    entry.add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass

    info = ZeroconfServiceInfo(
        ip_address="192.168.1.20",
        ip_addresses=["192.168.1.20"],
        hostname="test.local",
        name="_prana._tcp.local._test",
        type=SERVICE_TYPE,
        port=1234,
        properties={},
    )

    # Очікуємо, що discovery призведе до abort, якщо пристрій вже сконфігурований
    result = await flow.async_step_zeroconf(info)
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_zeroconf_new_device_and_confirm(hass: HomeAssistant) -> None:
    """Новий пристрій додається через zeroconf та підтверджується в confirm кроці."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.context = {"source": "zeroconf"}

    info = ZeroconfServiceInfo(
        ip_address="192.168.1.30",
        ip_addresses=["192.168.1.30"],
        hostname="prana.local",
        name="TestNew._prana._tcp.local.",
        type=SERVICE_TYPE,
        port=1234,
        properties={"label": "Prana Device", "config": {"mode": "eco"}},
    )

    # Крок zeroconf -> має повернути форму confirm
    result = await flow.async_step_zeroconf(info)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Підтвердження -> створення запису
    result2 = await flow.async_step_confirm(user_input={})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Prana Device"
    assert result2["data"][CONF_HOST] == "192.168.1.30"
    # CONF_CONFIG зберігає весь properties об'єкт
    assert result2["data"][CONF_CONFIG] == {
        "label": "Prana Device",
        "config": {"mode": "eco"},
    }
    assert result2["data"][CONF_MDNS] == "TestNew._prana._tcp.local."


@pytest.mark.asyncio
async def test_confirm_abort_no_devices(hass: HomeAssistant) -> None:
    """Abort, якщо confirm викликаний без попередньої discovery інформації."""
    flow = ConfigFlow()
    flow.hass = hass

    result = await flow.async_step_confirm()
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_user_flow_with_discovered_device(hass: HomeAssistant) -> None:
    """User flow should list discovered devices and allow choosing one."""
    # First, simulate zeroconf discovery to populate hass.data[DOMAIN + "_discovered"]
    flow_discover = ConfigFlow()
    flow_discover.hass = hass

    mdns_name = "DeviceOne._prana._tcp.local."
    info = ZeroconfServiceInfo(
        ip_address="192.168.1.40",
        ip_addresses=["192.168.1.40"],
        hostname="deviceone.local",
        name=mdns_name,
        type=SERVICE_TYPE,
        port=1234,
        properties={"label": "Device One", "config": {"mode": "auto"}},
    )

    # run zeroconf handler -> discovered stored
    result = await flow_discover.async_step_zeroconf(info)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Now start a user flow which should present the discovered device
    flow_user = ConfigFlow()
    flow_user.hass = hass

    # Initial call returns a form listing choices
    result_user = await flow_user.async_step_user()
    assert result_user["type"] == FlowResultType.FORM
    assert result_user["step_id"] == "user"

    # Submit the selected mdns to create the entry
    result_create = await flow_user.async_step_user(user_input={"mdns": mdns_name})
    assert result_create["type"] == FlowResultType.CREATE_ENTRY
    assert result_create["title"] == "Device One"
    assert result_create["data"][CONF_HOST] == "192.168.1.40"
    assert result_create["data"]["mdns"] == mdns_name
    assert result_create["data"]["config"] == {
        "label": "Device One",
        "config": {"mode": "auto"},
    }


@pytest.mark.asyncio
async def test_user_flow_abort_when_no_discovered_devices(hass: HomeAssistant) -> None:
    """User flow must abort with no_devices_found if nothing was discovered."""
    flow = ConfigFlow()
    flow.hass = hass

    # Ensure no discovered devices in hass.data
    hass.data.pop("prana_discovered", None)

    result = await flow.async_step_user()
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_found"
