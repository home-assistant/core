"""Constants for weheat tests."""

from weheat.abstractions import HeatPumpDiscovery

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
HEAT_PUMP_INFO = "heat_pump_info"
NO_PUMP_FOUND = []
SINGLE_PUMP_FOUND = [
    HeatPumpDiscovery.HeatPumpInfo(
        uuid="some-random-uuid",
        name="Hass name",
        model="BlackBird P80 heat pump",
        sn="SN-1234-5678",
        has_dhw=False,
    )
]
TWO_PUMPS_FOUND = [
    HeatPumpDiscovery.HeatPumpInfo(
        uuid="some-random-uuid-1",
        name="Hass name",
        model="BlackBird P80 heat pump",
        sn="SN-1234-5678",
        has_dhw=False,
    ),
    HeatPumpDiscovery.HeatPumpInfo(
        uuid="some-random-uuid-2",
        name="Hass different name",
        model="BlackBird P60 heat pump",
        sn="SN-8765-4321",
        has_dhw=True,
    ),
]
SELECT_PUMP_OPTION = [0, 1]
