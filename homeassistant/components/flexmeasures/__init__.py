"""The FlexMeasures integration."""
from __future__ import annotations

from datetime import timedelta
import json

from flexmeasures_client.client import FlexMeasuresClient
from flexmeasures_client.s2.cem import CEM
from flexmeasures_client.s2.control_types.FRBC.frbc_simple import FRBCSimple
from flexmeasures_client.s2.python_s2_protocol.common.schemas import ControlType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import S2FlexMeasuresClient, async_register_s2_api
from .const import DOMAIN
from .websockets import WebsocketAPIView

ATTR_NAME = "name"
DEFAULT_NAME = "World"


def setup(hass: HomeAssistant, config):
    """Set up is called when Home Assistant is loading our component."""

    # Return boolean to indicate that initialization was successful.
    return True


# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FlexMeasures from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    # TODO 1. Create API instance
    # TODO 2. Validate the API connection (and authentication)
    # TODO 3. Store an API object for your platforms to access
    coordinator = S2FlexMeasuresClient()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    def handle_api(call):
        """Handle the service call to the FlexMeasures REST API."""
        name = call.data.get(ATTR_NAME, DEFAULT_NAME)

        hass.states.set("flexmeasures_api.schedule", name)

    def handle_s2(call):
        """Handle the service call to the FlexMeasures S2 websockets implementation."""
        name = call.data.get(ATTR_NAME, DEFAULT_NAME)

        hass.states.set("flexmeasures_s2.message", name)

    # Register services
    hass.services.async_register(DOMAIN, "api", handle_api)
    hass.services.async_register(DOMAIN, "s2", handle_s2)
    async_register_s2_api(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    """Initialize the websocket API."""
    # TODO: create CEM in __init__ just once, when CEM supports multiple RMs
    fm_client = FlexMeasuresClient(
        "toy-password", "toy-user@flexmeasures.io"
    )  # replace by helpers/get_fm_client

    cem = CEM(fm_client=fm_client)
    frbc = FRBCSimple(
        power_sensor_id=1,
        price_sensor_id=2,
        soc_sensor_id=4,
        rm_discharge_sensor_id=5,
        schedule_duration=timedelta(hours=24),
    )
    cem.register_control_type(frbc)

    async def change_control_type(call):
        # print(call)

        value = hass.states.get("flexmeasures_api.prueba")
        if value is not None:
            value = json.loads(value.state).get("a") + 1
        else:
            value = 0

        hass.states.async_set("flexmeasures_api.prueba", json.dumps({"a": value}))

        await cem.activate_control_type(
            control_type=ControlType.FILL_RATE_BASED_CONTROL
        )

        # check/wait that the control type is set properly
        # while cem._control_type != ControlType.FILL_RATE_BASED_CONTROL:
        #     print("waiting for the activation of the control type...")
        #     await asyncio.sleep(1)

        # print("CONTROL TYPE: ", cem._control_type)

    hass.http.register_view(WebsocketAPIView(cem))
    hass.services.async_register(DOMAIN, "change_control_type", change_control_type)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Remove services
    hass.services.async_remove(DOMAIN, "api")
    hass.services.async_remove(DOMAIN, "s2")

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
