"""Test the zabbix sensors."""

from datetime import timedelta
from typing import cast
from unittest.mock import MagicMock, patch

from zabbix_utils import APIRequestError

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.zabbix.const import DEFAULT_TRIGGER_NAME, DOMAIN, ZAPI
from homeassistant.components.zabbix.sensor import (
    async_zabbix_sensors as async_zabbix_sensors_test,
)
from homeassistant.const import CONF_URL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .const import (
    MOCK_ALL_HOSTS_TRIGGER_NAME,
    MOCK_CONFIG_DATA_SENSOR_TOKEN,
    MOCK_CONFIGURATION_SENSOR_DATA_INDIVIDUAL_NO_HOSTIDS,
    MOCK_CONFIGURATION_SENSOR_DATA_INDIVIDUAL_WITH_HOSTIDS,
    MOCK_CONFIGURATION_SENSOR_DATA_NO_INDIVIDUAL_NO_HOSTIDS,
    MOCK_CONFIGURATION_SENSOR_DATA_NO_NAME_NO_INDIVIDUAL_WITH_HOSTIDS,
    MOCK_CONFIGURATION_SENSOR_DATA_NO_TRIGGERS,
    MOCK_DATA,
    MOCK_URL,
    MOCK_ZABBIX_API_VERSION,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_async_setup_entry_zapi_is_None(
    hass: HomeAssistant,
) -> None:
    """Test the async_setup_entry from mocked config entry when ZabbixAPI failed."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA_SENSOR_TOKEN,
        title="Zabbix integration",
        entry_id="mock_entry",
    )
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {ZAPI: None}
    await async_zabbix_sensors_test(hass, cast(ConfigType, entry), entry.entry_id)


async def test_async_setup_entry(
    hass: HomeAssistant,
) -> None:
    """Test the async_setup_entry from mocked config entry, including he async_setup_entry from __init__.py."""

    with (
        patch(
            "homeassistant.components.zabbix.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)
        mock_instance_api.host.get = MagicMock(
            side_effect=[
                [{"name": "host_1"}],
                [{"name": "host_2"}],
            ]
        )
        mock_instance_api.login = MagicMock()
        mock_instance_api.check_auth = MagicMock()
        # Mocking that each host has 5 triggers problems
        mock_instance_api.trigger.get = MagicMock(
            return_value=["1", "2", "3", "4", "5"]
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG_DATA_SENSOR_TOKEN,
            title="Zabbix integration",
            entry_id="mock_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        sensors = hass.states.async_all(domain_filter=SENSOR_DOMAIN)
        assert len(sensors) == 2
        assert hass.states.is_state("sensor.zabbix_host_1", "5") is True
        assert hass.states.is_state("sensor.zabbix_host_2", "5") is True


async def test_async_setup_platform_no_zapi(hass: HomeAssistant) -> None:
    """Test the sensor setup failure when no zabbix api set."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = MOCK_DATA

    # Test if zapi is not defined
    config = MOCK_CONFIGURATION_SENSOR_DATA_NO_TRIGGERS
    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()
    # check that no sensor is actually added for zabbix domain
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 0


async def test_async_setup_platform_no_full_config(hass: HomeAssistant) -> None:
    """Test the sensor setup from mocked configuration.yaml entry. Old way for backward compatibility."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = MOCK_DATA

    hass.data[DOMAIN][ZAPI] = MagicMock().return_value
    mock_instance_api = hass.data[DOMAIN][ZAPI]
    hass.data[DOMAIN][CONF_URL] = MOCK_URL
    mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)

    # Testing if sensor is created when no data in  triggers section in configuration
    config = MOCK_CONFIGURATION_SENSOR_DATA_NO_TRIGGERS

    # Sub test that sensor get data on update, as we have update_before_add=True
    # Assume we have 2 active triggers. Exact return list no matter as we are using len()
    mock_instance_api.trigger.get = MagicMock(return_value=["1", "2"])
    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()
    entity_id = "sensor." + DOMAIN + "_" + DEFAULT_TRIGGER_NAME
    assert hass.states.is_state(entity_id, "2") is True

    # Sub test with zabbix api exception on update
    mock_instance_api.trigger.get = MagicMock(
        side_effect=APIRequestError("error"),
    )

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=300))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE) is True


async def test_async_setup_platform_full_config_error_on_update(
    hass: HomeAssistant,
) -> None:
    """Test the sensor setup from mocked configuration.yaml entry. Old way for backward compatibility."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = MOCK_DATA

    hass.data[DOMAIN][ZAPI] = MagicMock().return_value
    mock_instance_api = hass.data[DOMAIN][ZAPI]
    hass.data[DOMAIN][CONF_URL] = MOCK_URL
    mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)

    # Testing if sensor is not created due to zappit host.get api error
    config = MOCK_CONFIGURATION_SENSOR_DATA_NO_NAME_NO_INDIVIDUAL_WITH_HOSTIDS
    mock_instance_api.host.get = MagicMock(side_effect=APIRequestError("error"))
    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 0


async def test_async_setup_platform_full_config_no_individual_with_hostids(
    hass: HomeAssistant,
) -> None:
    """Test the sensor setup from mocked configuration.yaml entry. Old way for backward compatibility."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = MOCK_DATA

    hass.data[DOMAIN][ZAPI] = MagicMock().return_value
    mock_instance_api = hass.data[DOMAIN][ZAPI]
    hass.data[DOMAIN][CONF_URL] = MOCK_URL
    mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)

    # Testing if only 1 sensor is created with the name of zabbix hostnames combined
    config = MOCK_CONFIGURATION_SENSOR_DATA_NO_NAME_NO_INDIVIDUAL_WITH_HOSTIDS
    mock_instance_api.host.get = MagicMock(
        return_value=[{"name": "host_1"}, {"name": "host_2"}, {"name": "host_3"}]
    )
    mock_instance_api.trigger.get = MagicMock(return_value=["1", "2", "3"])
    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()
    sensors = hass.states.async_all(domain_filter=SENSOR_DOMAIN)
    assert len(sensors) == 1

    entity_id = "sensor." + DOMAIN + "_host_1_host_2_host_3"
    assert hass.states.is_state(entity_id, "3") is True


async def test_async_setup_platform_full_config_no_individual_no_hostids(
    hass: HomeAssistant,
) -> None:
    """Test the sensor setup from mocked configuration.yaml entry. Old way for backward compatibility."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = MOCK_DATA

    hass.data[DOMAIN][ZAPI] = MagicMock().return_value
    mock_instance_api = hass.data[DOMAIN][ZAPI]
    hass.data[DOMAIN][CONF_URL] = MOCK_URL
    mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)

    # Testing if only 1 sensor is created with the provided name if no hostids
    config = MOCK_CONFIGURATION_SENSOR_DATA_NO_INDIVIDUAL_NO_HOSTIDS
    mock_instance_api.trigger.get = MagicMock(return_value=["1", "2", "3", "4"])
    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()
    sensors = hass.states.async_all(domain_filter=SENSOR_DOMAIN)
    assert len(sensors) == 1

    entity_id = (
        "sensor." + DOMAIN + "_" + MOCK_ALL_HOSTS_TRIGGER_NAME.lower().replace(" ", "_")
    )
    assert hass.states.is_state(entity_id, "4") is True


async def test_async_setup_platform_full_config_individual_no_hostids(
    hass: HomeAssistant,
) -> None:
    """Test the sensor setup from mocked configuration.yaml entry. Old way for backward compatibility."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = MOCK_DATA

    hass.data[DOMAIN][ZAPI] = MagicMock().return_value
    mock_instance_api = hass.data[DOMAIN][ZAPI]
    hass.data[DOMAIN][CONF_URL] = MOCK_URL
    mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)

    # Testing if sensor is not created
    config = MOCK_CONFIGURATION_SENSOR_DATA_INDIVIDUAL_NO_HOSTIDS
    #    mock_instance_api.trigger.get = MagicMock(return_value=["1", "2", "3", "4"])
    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()
    sensors = hass.states.async_all(domain_filter=SENSOR_DOMAIN)
    assert len(sensors) == 0


async def test_async_setup_platform_full_config_individual_with_hostids(
    hass: HomeAssistant,
) -> None:
    """Test the sensor setup from mocked configuration.yaml entry. Old way for backward compatibility."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = MOCK_DATA

    hass.data[DOMAIN][ZAPI] = MagicMock().return_value
    mock_instance_api = hass.data[DOMAIN][ZAPI]
    hass.data[DOMAIN][CONF_URL] = MOCK_URL
    mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)

    # Testing if 5 sensors are created with the names mocked
    config = MOCK_CONFIGURATION_SENSOR_DATA_INDIVIDUAL_WITH_HOSTIDS

    mock_instance_api.host.get = MagicMock(
        side_effect=[
            [{"name": "host_1"}],
            [{"name": "host_2"}],
            [{"name": "host_3"}],
            [{"name": "host_4"}],
            [{"name": "host_5"}],
        ]
    )
    # Mocking that each host has 5 triggers problems
    mock_instance_api.trigger.get = MagicMock(return_value=["1", "2", "3", "4", "5"])
    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()
    sensors = hass.states.async_all(domain_filter=SENSOR_DOMAIN)
    assert len(sensors) == 5
    for X in range(1, 6, 1):
        entity_id = "sensor." + DOMAIN + "_" + "host_" + str(X)
        assert hass.states.is_state(entity_id, "5") is True


async def test_async_setup_platform_full_config_individual_with_hostids_but_zabbix_error(
    hass: HomeAssistant,
) -> None:
    """Test the sensor setup from mocked configuration.yaml entry. Old way for backward compatibility."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = MOCK_DATA

    hass.data[DOMAIN][ZAPI] = MagicMock().return_value
    mock_instance_api = hass.data[DOMAIN][ZAPI]
    hass.data[DOMAIN][CONF_URL] = MOCK_URL
    mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)

    # Testing if 5 sensors are created with the names mocked
    config = MOCK_CONFIGURATION_SENSOR_DATA_INDIVIDUAL_WITH_HOSTIDS

    mock_instance_api.host.get = MagicMock(side_effect=APIRequestError("error"))
    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()
    sensors = hass.states.async_all(domain_filter=SENSOR_DOMAIN)
    # Test that no sensors got created
    assert len(sensors) == 0
