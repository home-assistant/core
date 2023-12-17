"""Helper functions to relate sensors keys and unique ids."""
from aiopvpc.const import (
    ALL_SENSORS,
    KEY_INJECTION,
    KEY_MAG,
    KEY_OMIE,
    KEY_PVPC,
    TARIFFS,
)

_ha_uniqueid_to_sensor_key = {
    TARIFFS[0]: KEY_PVPC,
    TARIFFS[1]: KEY_PVPC,
    f"{TARIFFS[0]}_{KEY_INJECTION}": KEY_INJECTION,
    f"{TARIFFS[1]}_{KEY_INJECTION}": KEY_INJECTION,
    f"{TARIFFS[0]}_{KEY_MAG}": KEY_MAG,
    f"{TARIFFS[1]}_{KEY_MAG}": KEY_MAG,
    f"{TARIFFS[0]}_{KEY_OMIE}": KEY_OMIE,
    f"{TARIFFS[1]}_{KEY_OMIE}": KEY_OMIE,
}


def get_enabled_sensor_keys(
    using_private_api: bool, disabled_sensor_ids: list[str]
) -> set[str]:
    """(HA) Get enabled API indicators."""
    sensor_keys = set(ALL_SENSORS) if using_private_api else {KEY_PVPC}
    for unique_id in disabled_sensor_ids:
        disabled_ind = _ha_uniqueid_to_sensor_key[unique_id]
        if disabled_ind in sensor_keys:
            sensor_keys.remove(disabled_ind)

    return sensor_keys


def make_sensor_unique_id(config_entry_id: str | None, sensor_key: str) -> str:
    """Generate unique_id for each sensor kind and config entry."""
    assert sensor_key in ALL_SENSORS
    assert config_entry_id is not None
    if sensor_key == KEY_PVPC:
        # for old compatibility
        return config_entry_id
    return f"{config_entry_id}_{sensor_key}"
