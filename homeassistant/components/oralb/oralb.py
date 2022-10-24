"""OralB Parser."""
from struct import unpack


def parse_oral_b(data, rssi, mac):
    """Parser for Oral-B toothbrush."""
    states = {
        0: "unknown",
        1: "initializing",
        2: "idle",
        3: "running",
        4: "charging",
        5: "setup",
        6: "flight menu",
        8: "selection menu",
        113: "final test",
        114: "pcb test",
        115: "sleeping",
        116: "transport",
    }

    preasures = {114: "normal", 118: "button pressed", 178: "high"}
    modes = {
        0: "off",
        1: "daily clean",
        2: "sensitive",
        3: "massage",
        4: "whitening",
        5: "deep clean",
        6: "tongue cleaning",
        7: "turbo",
        255: "unknown",
    }
    device_type = "SmartSeries 7000"

    result = {
        "state": None,
        "pressure": None,
        "counter": None,
        "mode": None,
        "sector": None,
        "sector_timer": None,
        "no_sectors": None,
        "rssi": rssi,
        "mac": mac,
        "device_type": None,
    }

    msg_length = len(data)
    if msg_length == 11:
        device_bytes = data[4:7]
        if device_bytes == b"\x062k":
            device_type = "IO Series 7"
            modes = {
                0: "daily clean",
                1: "sensitive",
                2: "gum care",
                3: "whiten",
                4: "intense",
                8: "settings",
            }
        (
            state,
            pressure,
            counter_m,
            counter_s,
            mode,
            sector,
            sector_timer,
            no_of_sectors,
        ) = unpack(">BBbbBBBB", data[3:11])
        counter = counter_m * 60 + counter_s

        result["state"] = states.get(state, f"unknown state {state}")
        result["mode"] = modes.get(mode, f"unknown mode {mode}")
        result["pressure"] = preasures.get(pressure, f"unknown pressure {pressure}")
        result["counter"] = counter

        if sector == 254:
            result["sector"] = "last sector"
        elif sector == 255:
            result["sector"] = "no sector"
        else:
            result["sector"] = str(sector)

        result["sector_timer"] = sector_timer
        result["no_sectors"] = no_of_sectors
        result["device_type"] = device_type

    return result
