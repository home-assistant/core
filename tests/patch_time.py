"""Compatibility imports for the Home Assistant pytest helpers."""

# ruff: noqa: PLC0414

from pytest_homeassistant.patch_time import (
    Any as Any,
    HAFakeDate as HAFakeDate,
    HAFakeDateMeta as HAFakeDateMeta,
    HAFakeDatetime as HAFakeDatetime,
    HAFakeDatetimeMeta as HAFakeDatetimeMeta,
    _ha_tz_offset as _ha_tz_offset,
    _monotonic as _monotonic,
    _utcnow as _utcnow,
    dt as dt,
    dt_util as dt_util,
    event_helper as event_helper,
    freezegun as freezegun,
    ha_datetime_to_fakedatetime as ha_datetime_to_fakedatetime,
    ha_get_current_time as ha_get_current_time,
    ha_get_module_attributes as ha_get_module_attributes,
    ha_get_module_attributes_hash as ha_get_module_attributes_hash,
    ha_should_use_real_time as ha_should_use_real_time,
    inspect as inspect,
    runner as runner,
    time as time,
    types as types,
    util as util,
)
