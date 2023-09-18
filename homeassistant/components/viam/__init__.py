"""The viam integration."""
from __future__ import annotations

from datetime import datetime, timedelta

from viam.app.app_client import RobotPart
from viam.app.viam_client import ViamClient
from viam.rpc.dial import Credentials, DialOptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up viam from a config entry."""
    credentials = Credentials(
        type="robot-location-secret", payload=entry.data["secret"]
    )
    dial_options = DialOptions(
        auth_entity=entry.data["address"], credentials=credentials
    )
    viam_client = await ViamClient.create_from_dial_options(dial_options=dial_options)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = viam_client

    @callback
    async def send_data(time: datetime) -> None:
        """Send timing data to Viam."""
        robots = await viam_client.app_client.list_robots()
        parts: list[RobotPart] = await viam_client.app_client.get_robot_parts(
            robot_id=robots.pop().id
        )
        await viam_client.data_client.tabular_data_capture_upload(
            tabular_data=[{"current_time": str(time)}],
            part_id=parts.pop().id,
            component_type="sensor",
            component_name="time",
            method_name="get_readings",
            data_request_times=[[datetime.now(), datetime.now()]],
        )

    unsub = async_track_time_interval(
        hass, send_data, timedelta(seconds=10), name="Send data to Viam"
    )

    @callback
    def unsub_tack_time_interval(_event: Event) -> None:
        """Unsubscribe track time interval timer."""
        unsub()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unsub_tack_time_interval)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
    viam_client = hass.data[DOMAIN].pop(entry.entry_id)
    viam_client.close()

    return True
