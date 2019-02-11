"""The tests for the Google Wifi platform."""
import json
from unittest import mock

import requests_mock

import homeassistant.components.sensor.growatt as victim


def test_extract_single_energy():
    plant_info_data = [
        {'plantMoneyText': '137.9 ',
         'plantName': 'my plant',
         'plantId': '107658',
         'isHaveStorage': 'false',
         'todayEnergy': '0.6 kWh',
         'totalEnergy': '114.9 kWh',
         'currentPower': '142 W'}
    ]

    energy = (victim
              .GrowattPlant(None, None, None)
              ._extract_energy(plant_info_data, 'todayEnergy'))
    assert energy == 0.6


def test_extract_multiple_energy():
    plant_info_data = [
        {'plantMoneyText': '137.9 ',
         'plantName': 'my plant',
         'plantId': '107658',
         'isHaveStorage': 'false',
         'todayEnergy': '0.6 kWh',
         'totalEnergy': '114.9 kWh',
         'currentPower': '142 W'},
        {'plantMoneyText': '137.9 ',
         'plantName': 'my plant',
         'plantId': '107658',
         'isHaveStorage': 'false',
         'todayEnergy': '0.6 kWh',
         'totalEnergy': '114.9 kWh',
         'currentPower': '142 W'}
    ]

    energy = (victim
              .GrowattPlant(None, None, None)
              ._extract_energy(plant_info_data, 'todayEnergy'))
    assert energy == 1.2


@mock.patch('growatt.GrowattPlant.login',
            return_value=json.dumps({'back': {'userId': '1'}}))
def test_login(_):
    sensor = victim.GrowattPlant(None, 'foo', 'bar')
    login_res = sensor.client.login()
    assert login_res == {'userId': '1'}


@mock.patch('growatt.GrowattPlant.plant_detail',
            return_value=json.dumps({'back': {'data': 'some-data'}}))
def test_plant_list(_):
    sensor = victim.GrowattPlant(None, 'foo', 'bar')
    login_res = sensor.client.plant_detail('1')
    assert login_res == {'data': 'some-data'}


dummy_plant_info = {'data': [{'plantMoneyText': '137.9 ',
                              'plantName': 'my plant',
                              'plantId': '107658',
                              'isHaveStorage': 'false',
                              'todayEnergy': '0.6 kWh',
                              'totalEnergy': '114.9 kWh',
                              'currentPower': '142 W'}],
                    'totalData': {'currentPowerSum': '142 W',
                                  'CO2Sum': '114.9 T',
                                  'isHaveStorage': 'false',
                                  'eTotalMoneyText': '137.9 ',
                                  'todayEnergySum': '0.6 kWh',
                                  'totalEnergySum': '114.9 kWh'},
                    'success': True}


@mock.patch('growatt.GrowattPlant.login',
            return_value=json.dumps({'back': {'userId': '1'}}))
@mock.patch('growatt.GrowattPlant.plant_list',
            return_value=json.dumps(dummy_plant_info))
def test_today_energy_total(_, __):
    with requests_mock.mock() as m:
        m.get('https://server.growatt.com/PlantListAPI.do?userId=1',
              text=json.dumps({'back': dummy_plant_info}))

        energy_total = (victim
                        .GrowattPlant(None, 'foo', 'bar')
                        .todays_energy_total('foo', 'bar'))
        assert energy_total == 0.6
