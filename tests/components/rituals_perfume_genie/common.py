"""Common methods used across tests for Rituals Perfume Genie."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, create_autospec, patch

from pytest_homeassistant.common import MockConfigEntry
from ritualsgenie import (
    RitualsGenie,
    RitualsGenieHub,
    RitualsGenieHublot,
    RitualsGenieSensor,
    RitualsGenieSensors,
    Sensor,
)

from homeassistant.components.rituals_perfume_genie.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

ROOM_SIZES = {15: "1", 30: "2", 60: "3", 100: "4"}
SENSOR_FIELDS = {
    "battery": Sensor.BATTERY,
    "fill": Sensor.FILL,
    "perfume": Sensor.PERFUME,
    "wifi": Sensor.WIFI,
}
WIFI_ICONS = {
    100: "icon-signal.png",
    75: "icon-signal-75.png",
    25: "icon-signal-low.png",
}


def mock_config_entry(unique_id: str, entry_id: str = "an_entry_id") -> MockConfigEntry:
    """Return a mock Config Entry for the Rituals Perfume Genie integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="name@example.com",
        unique_id=unique_id,
        data={
            CONF_EMAIL: "test@rituals.com",
            CONF_PASSWORD: "test-password",
        },
        version=2,
        entry_id=entry_id,
    )


@dataclass
class MockDiffuser:
    """A diffuser, as the API would report it right now."""

    hublot: str
    available: bool = True
    charging: bool = True
    fill: str | None = "90-100%"
    # A use counter on the cartridge: 200 per percent used, so this is 95%.
    fill_raw: str = "1000"
    has_battery: bool = True
    has_cartridge: bool = True
    is_on: bool = True
    model: str = "Genie 2.0"
    name: str = "Genie"
    perfume: str = "Ritual of Sakura"
    perfume_amount: int = 2
    room_size_square_meter: int = 60
    has_square_meters: bool = True
    standby_led: bool | None = True
    version: str | None = "4.0"
    firmware_id: int | None = 127
    has_firmware_info: bool = True
    newest_version: str | None = None
    newest_firmware_id: int | None = None
    wifi_percentage: int = 75
    battery_percentage: int = field(default=100, init=False)

    @property
    def hub_hash(self) -> str:
        """Return the hash of the diffuser."""
        return f"hash-{self.hublot}"

    def hub(self) -> RitualsGenieHub:
        """Return the hub, as the API would send it."""
        return RitualsGenieHub.from_dict(
            {
                "hash": self.hub_hash,
                "hublot": self.hublot,
                "status": 1 if self.available else 0,
                "attributes": {
                    "ledc": self.standby_led is not None,
                    "squaremeterc": self.has_square_meters,
                },
                "attributeValues": {
                    "fanc": "1" if self.is_on else "0",
                    "speedc": str(self.perfume_amount),
                    "roomc": ROOM_SIZES[self.room_size_square_meter],
                    "squaremeterc": str(self.room_size_square_meter),
                    "roomnamec": self.name,
                    # Inverted: the attribute means "LED disabled".
                    "ledc": "1" if self.standby_led is False else "0",
                },
                "sensors": {
                    "battc": self.has_battery,
                    "fillc": self.fill is not None,
                    "rfidc": True,
                    "versionc": True,
                    "wific": True,
                },
                "firmwareInfo": (
                    {
                        "currentFirmware": self.version,
                        "currentFirmwareId": self.firmware_id,
                        "newestFirmware": self.newest_version or self.version,
                        "newestFirmwareId": self.newest_firmware_id or self.firmware_id,
                    }
                    if self.has_firmware_info
                    else None
                ),
            }
        )

    def hardware(self) -> RitualsGenieHublot:
        """Return the hardware details, as the API would send them."""
        return RitualsGenieHublot.from_dict(
            {"deviceVersion": self.model, "hubHash": self.hub_hash}
        )

    def sensors(self, only: Iterable[Sensor] | None = None) -> RitualsGenieSensors:
        """Return the sensor readings, as the API would send them."""
        wanted = set(Sensor) if only is None else set(only)
        readings = {
            "battery": (
                RitualsGenieSensor(
                    icon="battery-full.png", id=21 if self.charging else 1
                )
                if self.has_battery
                else None
            ),
            "fill": self.sensor(Sensor.FILL) if self.fill else None,
            "perfume": self.sensor(Sensor.PERFUME),
            "wifi": RitualsGenieSensor(icon=WIFI_ICONS[self.wifi_percentage]),
        }
        return RitualsGenieSensors(
            **{
                field: reading
                for field, reading in readings.items()
                if SENSOR_FIELDS[field] in wanted
            }
        )

    def sensor(self, sensor: Sensor) -> RitualsGenieSensor:
        """Return a single sensor reading, as the API would send it."""
        if sensor is Sensor.FILL:
            return RitualsGenieSensor(title=self.fill, raw=self.fill_raw)

        return RitualsGenieSensor(
            title=self.perfume, raw="048616d0" if self.has_cartridge else "0"
        )


def mock_diffuser(hublot: str, **kwargs: Any) -> MockDiffuser:
    """Return a mock diffuser initialized with the given data."""
    return MockDiffuser(hublot=hublot, **kwargs)


def mock_diffuser_v1_battery_cartridge() -> MockDiffuser:
    """Create and return a mock version 1 Diffuser with battery and a cartridge."""
    return mock_diffuser(hublot="lot123v1")


def mock_diffuser_v3_no_battery_no_fill() -> MockDiffuser:
    """Create and return a mock version 3 Diffuser without battery or fill sensor."""
    return mock_diffuser(
        hublot="lot123v3",
        fill=None,
        has_battery=False,
        has_cartridge=True,
        name="Genie V3",
        perfume="Ritual of Sakura",
        version="6.0",
    )


def mock_diffuser_v2_no_battery_no_cartridge() -> MockDiffuser:
    """Create and return a mock version 2 Diffuser without battery and cartridge."""
    return mock_diffuser(
        hublot="lot123v2",
        has_battery=False,
        has_cartridge=False,
        name="Genie V2",
        perfume="Cartridge is not loaded",
        version="5.0",
    )


def mock_client(diffusers: list[MockDiffuser]) -> AsyncMock:
    """Return a mock client that answers with the given diffusers.

    Diffusers are looked up on every call, as a test may add one to the
    account later on.
    """

    def by_hash(hub_hash: str) -> MockDiffuser:
        return next(diffuser for diffuser in diffusers if diffuser.hub_hash == hub_hash)

    def by_hublot(hublot: str) -> MockDiffuser:
        return next(diffuser for diffuser in diffusers if diffuser.hublot == hublot)

    client = create_autospec(RitualsGenie, instance=True)
    client.token = "mock-token"
    client.hubs.side_effect = lambda: [diffuser.hub() for diffuser in diffusers]
    client.hub.side_effect = lambda hub_hash: by_hash(hub_hash).hub()
    client.hublot.side_effect = lambda hublot: by_hublot(hublot).hardware()
    client.sensors.side_effect = lambda hub, only=None: by_hash(hub.hash).sensors(only)
    client.sensor.side_effect = lambda hub_hash, sensor: by_hash(hub_hash).sensor(
        sensor
    )

    return client


async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_diffusers: list[MockDiffuser],
) -> AsyncMock:
    """Initialize Rituals Perfume Genie with given entry and diffusers."""
    mock_config_entry.add_to_hass(hass)
    client = mock_client(mock_diffusers)

    with patch(
        "homeassistant.components.rituals_perfume_genie.RitualsGenie",
        return_value=client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data

    return client
