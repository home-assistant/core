"""Common test code."""
from typing import List, NamedTuple, Optional
from unittest.mock import MagicMock, Mock

from gogogate2_api import GogoGate2Api, InfoResponse
from gogogate2_api.common import Door, DoorMode, DoorStatus, Network, Outputs, Wifi

from homeassistant.components import persistent_notification
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.gogogate2 import async_unload_entry
from homeassistant.components.gogogate2.common import (
    GogoGateDataUpdateCoordinator,
    get_data_update_coordinator,
)
import homeassistant.components.gogogate2.const as const
from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_UNIT_SYSTEM, CONF_UNIT_SYSTEM_METRIC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.setup import async_setup_component

INFO_RESPONSE = InfoResponse(
    user="user1",
    gogogatename="gogogatename1",
    model="",
    apiversion="",
    remoteaccessenabled=False,
    remoteaccess="abcdefg.my-gogogate.com",
    firmwareversion="",
    apicode="API_CODE",
    door1=Door(
        door_id=1,
        permission=True,
        name="Door1",
        mode=DoorMode.GARAGE,
        status=DoorStatus.OPENED,
        sensor=True,
        sensorid=None,
        camera=False,
        events=2,
        temperature=None,
    ),
    door2=Door(
        door_id=2,
        permission=True,
        name=None,
        mode=DoorMode.GARAGE,
        status=DoorStatus.OPENED,
        sensor=True,
        sensorid=None,
        camera=False,
        events=2,
        temperature=None,
    ),
    door3=Door(
        door_id=3,
        permission=True,
        name="Door3",
        mode=DoorMode.GARAGE,
        status=DoorStatus.OPENED,
        sensor=True,
        sensorid=None,
        camera=False,
        events=2,
        temperature=None,
    ),
    outputs=Outputs(output1=True, output2=False, output3=True),
    network=Network(ip=""),
    wifi=Wifi(SSID="", linkquality="", signal=""),
)


class ComponentData(NamedTuple):
    """Test data for a mocked component."""

    api: GogoGate2Api
    data_update_coordinator: GogoGateDataUpdateCoordinator


class ComponentFactory:
    """Manages the setup and unloading of the withing component and profiles."""

    def __init__(self, hass: HomeAssistant, gogogate_api_mock: Mock) -> None:
        """Initialize the object."""
        self._hass = hass
        self._gogogate_api_mock = gogogate_api_mock

    @property
    def api_class_mock(self):
        """Get the api class mock."""
        return self._gogogate_api_mock

    async def configure_component(
        self, cover_config: Optional[List[dict]] = None
    ) -> None:
        """Configure the component."""
        hass_config = {
            "homeassistant": {CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC},
            "cover": cover_config or [],
        }

        await async_process_ha_core_config(self._hass, hass_config.get("homeassistant"))
        assert await async_setup_component(self._hass, HA_DOMAIN, {})
        assert await async_setup_component(
            self._hass, persistent_notification.DOMAIN, {}
        )
        assert await async_setup_component(self._hass, COVER_DOMAIN, hass_config)
        assert await async_setup_component(self._hass, const.DOMAIN, hass_config)
        await self._hass.async_block_till_done()

    async def run_config_flow(
        self, config_data: dict, api_mock: Optional[GogoGate2Api] = None
    ) -> ComponentData:
        """Run a config flow."""
        if api_mock is None:
            api_mock: GogoGate2Api = MagicMock(spec=GogoGate2Api)
            api_mock.info.return_value = INFO_RESPONSE

        self._gogogate_api_mock.reset_mocks()
        self._gogogate_api_mock.return_value = api_mock

        result = await self._hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": SOURCE_USER}
        )
        assert result
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await self._hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=config_data,
        )
        assert result
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == config_data

        await self._hass.async_block_till_done()

        config_entry = next(
            iter(
                entry
                for entry in self._hass.config_entries.async_entries(const.DOMAIN)
                if entry.unique_id == "abcdefg"
            )
        )

        return ComponentData(
            api=api_mock,
            data_update_coordinator=get_data_update_coordinator(
                self._hass, config_entry
            ),
        )

    async def unload(self) -> None:
        """Unload all config entries."""
        config_entries = self._hass.config_entries.async_entries(const.DOMAIN)
        for config_entry in config_entries:
            await async_unload_entry(self._hass, config_entry)

        await self._hass.async_block_till_done()
        assert not self._hass.states.async_entity_ids("gogogate")
