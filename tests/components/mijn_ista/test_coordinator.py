"""Tests for mijn_ista coordinator — parsing functions and update logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from mijn_ista_api import MijnIstaAuthError, MijnIstaConnectionError

from custom_components.mijn_ista.const import CONF_UPDATE_INTERVAL, DOMAIN
from custom_components.mijn_ista.coordinator import (
    MijnIstaCoordinator,
    AnnualMeterSummary,
    AnnualSummary,
    CustomerData,
    DeviceConsumption,
    MonthEntry,
    MonthServiceData,
    ServiceInfo,
    _parse_annual_meter,
    _parse_customer,
    _parse_device_consumption,
)

from .conftest import MOCK_AVG_VALUES, MOCK_MONTH_VALUES, MOCK_USER_VALUES


# ---------------------------------------------------------------------------
# _parse_annual_meter
# ---------------------------------------------------------------------------


class TestParseAnnualMeter:
    def test_full_fields(self):
        raw = {
            "MeterId": 101,
            "serviceId": 1,
            "MeterNr": 12345,
            "ArtNr": 7,
            "BsDate": "2024-01-01T00:00:00",
            "BeginValue": 0.0,
            "EsDate": "2024-12-31T00:00:00",
            "EndValue": 42.5,
            "CValue": 42.5,
            "DecPos": 1,
        }
        result = _parse_annual_meter(raw)
        assert isinstance(result, AnnualMeterSummary)
        assert result.meter_id == 101
        assert result.service_id == 1
        assert result.serial_nr == 12345
        assert result.art_nr == 7
        assert result.begin_date == "2024-01-01T00:00:00"
        assert result.begin_value == 0.0
        assert result.end_date == "2024-12-31T00:00:00"
        assert result.end_value == 42.5
        assert result.c_value == 42.5
        assert result.dec_pos == 1

    def test_missing_optional_fields_use_defaults(self):
        raw = {"MeterId": 55, "serviceId": 3}
        result = _parse_annual_meter(raw)
        assert result.meter_id == 55
        assert result.serial_nr == 0
        assert result.art_nr == 0
        assert result.begin_date == ""
        assert result.begin_value == 0.0
        assert result.end_date == ""
        assert result.end_value == 0.0
        assert result.c_value == 0.0
        assert result.dec_pos == 0

    def test_as_dict_keys(self):
        raw = {
            "MeterId": 1,
            "serviceId": 2,
            "MeterNr": 9,
            "ArtNr": 0,
            "BsDate": "2024-01-01T00:00:00",
            "BeginValue": 1.0,
            "EsDate": "2024-06-30T00:00:00",
            "EndValue": 5.0,
            "CValue": 4.0,
            "DecPos": 0,
        }
        d = _parse_annual_meter(raw).as_dict()
        assert set(d.keys()) == {
            "meter_id", "service_id", "serial_nr", "art_nr",
            "begin_date", "begin_value", "end_date", "end_value", "consumption",
        }
        assert d["consumption"] == 4.0


# ---------------------------------------------------------------------------
# _parse_device_consumption
# ---------------------------------------------------------------------------


class TestParseDeviceConsumption:
    def test_full_fields(self):
        raw = {
            "Id": 201,
            "SerialNr": 67890,
            "ArtNr": 3,
            "SDate": "2024-11-01T00:00:00",
            "SValue": 16.5,
            "EDate": "2024-11-30T00:00:00",
            "EValue": 18.0,
            "CValue": 1.5,
            "CCDValue": 0.1,
            "Active": "2020-01-01T00:00:00",
            "MainDevice": {"id": 999},
        }
        result = _parse_device_consumption(raw)
        assert isinstance(result, DeviceConsumption)
        assert result.meter_id == 201
        assert result.serial_nr == 67890
        assert result.art_nr == 3
        assert result.s_date == "2024-11-01T00:00:00"
        assert result.s_value == 16.5
        assert result.e_date == "2024-11-30T00:00:00"
        assert result.e_value == 18.0
        assert result.c_value == 1.5
        assert result.ccd_value == 0.1
        assert result.active == "2020-01-01T00:00:00"
        assert result.main_device == {"id": 999}

    def test_missing_optional_fields_use_defaults(self):
        raw = {"Id": 42}
        result = _parse_device_consumption(raw)
        assert result.meter_id == 42
        assert result.serial_nr == 0
        assert result.c_value == 0.0
        assert result.main_device is None

    def test_as_dict_contains_consumption_key(self):
        raw = {
            "Id": 1, "SerialNr": 2, "ArtNr": 0,
            "SDate": "", "SValue": 0.0, "EDate": "", "EValue": 3.0,
            "CValue": 3.0, "CCDValue": 0.0, "Active": "",
        }
        d = _parse_device_consumption(raw).as_dict()
        assert d["consumption"] == 3.0
        assert d["main_device"] is None


# ---------------------------------------------------------------------------
# _parse_customer
# ---------------------------------------------------------------------------


class TestParseCustomer:
    @pytest.fixture
    def customer_data(self) -> CustomerData:
        cus = MOCK_USER_VALUES["Cus"][0]
        return _parse_customer(cus, MOCK_MONTH_VALUES, MOCK_AVG_VALUES)

    def test_basic_fields(self, customer_data):
        assert customer_data.cuid == "test-cuid-abc123"
        assert customer_data.address == "Teststraat 1"
        assert customer_data.zip_code == "1234 AB"
        assert customer_data.city == "Amsterdam"

    def test_services_parsed(self, customer_data):
        assert len(customer_data.services) == 2
        svc_ids = {s.id for s in customer_data.services}
        assert svc_ids == {1, 2}
        heating = next(s for s in customer_data.services if s.id == 1)
        assert heating.description == "Verwarming"
        assert heating.unit == "Gigajoule"

    def test_annual_summaries(self, customer_data):
        assert 1 in customer_data.annual
        annual_heating = customer_data.annual[1]
        assert isinstance(annual_heating, AnnualSummary)
        assert annual_heating.total_now == 42.5
        assert annual_heating.total_previous == 48.0
        assert annual_heating.diff_pct == -11.5
        assert len(annual_heating.cur_meters) == 1
        assert annual_heating.cur_meters[0].meter_id == 101

    def test_monthly_entries(self, customer_data):
        assert len(customer_data.monthly) == 2
        latest = customer_data.monthly[0]
        assert isinstance(latest, MonthEntry)
        assert latest.year == 2024
        assert latest.month == 11
        assert latest.avg_temp == 8.2
        assert 1 in latest.services

    def test_null_avg_temp_becomes_none(self, customer_data):
        # Second month has at=None in fixture
        second = customer_data.monthly[1]
        assert second.avg_temp is None

    def test_building_averages(self, customer_data):
        assert customer_data.building_averages[1] == 46.0
        assert customer_data.building_averages[2] == 19.5

    def test_billing_period_temperatures(self, customer_data):
        # Sorted descending by year → 2024 is current, 2023 is previous
        assert customer_data.cur_period_temp == 10.5
        assert customer_data.prev_period_temp == 9.8

    def test_monthly_service_data(self, customer_data):
        latest = customer_data.monthly[0]
        svc1 = latest.services[1]
        assert isinstance(svc1, MonthServiceData)
        assert svc1.total_consumption == 4.2
        assert svc1.building_average == 5.0
        assert svc1.has_approximation is False
        assert len(svc1.device_consumptions) == 1
        assert svc1.device_consumptions[0].c_value == 4.2

    def test_empty_month_data(self):
        cus = MOCK_USER_VALUES["Cus"][0]
        result = _parse_customer(cus, {"mc": []}, {"Averages": []})
        assert result.monthly == []
        assert result.building_averages == {}

    def test_zero_avg_temp_becomes_none(self):
        """avg_temp of 0 should be treated as None (KNMI data not yet available)."""
        cus = MOCK_USER_VALUES["Cus"][0]
        month_data = {
            "mc": [{"y": 2024, "m": 11, "at": 0, "ServiceConsumptions": []}]
        }
        result = _parse_customer(cus, month_data, {"Averages": []})
        assert result.monthly[0].avg_temp is None

    def test_missing_billing_periods_temperatures_are_none(self):
        """If no billing periods exist, period temps should be None."""
        import copy
        cus = copy.deepcopy(MOCK_USER_VALUES["Cus"][0])
        cus["curConsumption"]["BillingPeriods"] = []
        result = _parse_customer(cus, {"mc": []}, {"Averages": []})
        assert result.cur_period_temp is None
        assert result.prev_period_temp is None

    def test_single_billing_period_prev_temp_is_none(self):
        """With only one billing period, previous temp should be None."""
        import copy
        cus = copy.deepcopy(MOCK_USER_VALUES["Cus"][0])
        cus["curConsumption"]["BillingPeriods"] = [
            {"y": 2024, "s": "2024-01-01T00:00:00", "e": "2024-12-31T00:00:00", "ta": 10.5}
        ]
        result = _parse_customer(cus, {"mc": []}, {"Averages": []})
        assert result.cur_period_temp == 10.5
        assert result.prev_period_temp is None

    def test_annual_meter_as_dict(self, customer_data):
        meter = customer_data.annual[1].cur_meters[0]
        d = meter.as_dict()
        assert d["meter_id"] == 101
        assert d["consumption"] == 42.5

    def test_device_consumption_as_dict(self, customer_data):
        dev = customer_data.monthly[0].services[1].device_consumptions[0]
        d = dev.as_dict()
        assert d["consumption"] == 4.2
        assert d["serial_nr"] == 12345


# ---------------------------------------------------------------------------
# MijnIstaCoordinator._async_update_data
# ---------------------------------------------------------------------------


class TestCoordinatorUpdate:
    @pytest.fixture
    def mock_api(self):
        api = MagicMock()
        api.authenticate = AsyncMock()
        api.get_user_values = AsyncMock(return_value=MOCK_USER_VALUES)
        api.get_month_values = AsyncMock(return_value=MOCK_MONTH_VALUES)
        api.get_consumption_averages = AsyncMock(return_value=MOCK_AVG_VALUES)
        return api

    @pytest.fixture
    def mock_entry(self):
        entry = MagicMock()
        entry.data = {}
        entry.options = {CONF_UPDATE_INTERVAL: 24}
        entry.entry_id = "test-entry-id"
        return entry

    async def test_successful_update_returns_customer_data(
        self, hass: HomeAssistant, mock_api, mock_entry
    ):
        coord = MijnIstaCoordinator(hass, mock_entry, mock_api)
        result = await coord._async_update_data()
        assert "test-cuid-abc123" in result
        customer = result["test-cuid-abc123"]
        assert customer.address == "Teststraat 1"
        assert len(customer.services) == 2

    async def test_auth_error_raises_config_entry_auth_failed(
        self, hass: HomeAssistant, mock_api, mock_entry
    ):
        mock_api.authenticate = AsyncMock(side_effect=MijnIstaAuthError("bad creds"))
        coord = MijnIstaCoordinator(hass, mock_entry, mock_api)
        with pytest.raises(ConfigEntryAuthFailed):
            await coord._async_update_data()

    async def test_connection_error_raises_update_failed(
        self, hass: HomeAssistant, mock_api, mock_entry
    ):
        mock_api.get_user_values = AsyncMock(
            side_effect=MijnIstaConnectionError("timeout")
        )
        coord = MijnIstaCoordinator(hass, mock_entry, mock_api)
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    async def test_multiple_properties_all_returned(
        self, hass: HomeAssistant, mock_api, mock_entry
    ):
        second_cus = {**MOCK_USER_VALUES["Cus"][0], "Cuid": "second-cuid-xyz"}
        user_data = {**MOCK_USER_VALUES, "Cus": [MOCK_USER_VALUES["Cus"][0], second_cus]}
        mock_api.get_user_values = AsyncMock(return_value=user_data)
        coord = MijnIstaCoordinator(hass, mock_entry, mock_api)
        result = await coord._async_update_data()
        assert len(result) == 2
        assert "second-cuid-xyz" in result

    async def test_no_billing_periods_skips_averages(
        self, hass: HomeAssistant, mock_api, mock_entry
    ):
        import copy
        user_data = copy.deepcopy(MOCK_USER_VALUES)
        user_data["Cus"][0]["curConsumption"]["BillingPeriods"] = []
        mock_api.get_user_values = AsyncMock(return_value=user_data)
        coord = MijnIstaCoordinator(hass, mock_entry, mock_api)
        result = await coord._async_update_data()
        # Should still return data, just with empty building averages
        assert "test-cuid-abc123" in result
        assert result["test-cuid-abc123"].building_averages == {}
