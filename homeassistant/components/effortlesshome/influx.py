from influxdb_client import InfluxDBClient
import json

import yaml
import requests
import aiohttp
import asyncio
from .const import DOMAIN, DOMAIN
from homeassistant.core import (
    HomeAssistant,
    ServiceCall)

HA_URL = "http://homeassistant.local:8123"

async def process_trend_data(call: ServiceCall):
    """Handle the service call."""
    # device_id = call.data.get("device_id")

    geminikey = call.hass.data[DOMAIN]["ai_key"]

    # Fetch trend data
    trend_data = await get_trend_data(call)

    print(json.dumps(trend_data, indent=2))  # For debugging

    validate_automations(call)

    # Save to automations.yaml
    with open("automations.yaml", "w") as file:
        file.write(gemini_response)


# Query last 7 days of data
async def get_trend_data(call: ServiceCall):

    INFLUX_URL = call.hass.data[DOMAIN]["INFLUX_URL"]
    INFLUX_TOKEN = call.hass.data[DOMAIN]["INFLUX_TOKEN"]
    INFLUX_BUCKET = call.hass.data[DOMAIN]["INFLUX_BUCKET"]
    INFLUX_ORG = call.hass.data[DOMAIN]["INFLUX_ORG"]

    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -7d)
    '''

    #   query = f'''
    #       from(bucket: "{INFLUX_BUCKET}")
    #       |> range(start: -7d)
    #       |> filter(fn: (r) => r["_measurement"] == "sensor_data")
    #       |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    #       |> limit(n: 100)
    #   '''

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    result = await asyncio.to_thread(query_api.query, org=INFLUX_ORG, query=query)

    client.close()

    history = []
    for table in result:
        for record in table.records:
            history.append(
                {
                    "entity": record.get_field(),
                    "state": record.get_value(),
                    "time": record.get_time(),
                }
            )

    return history


def analyze_home_data(trend_data):
    prompt = f"""
    Given the following Home Assistant trend data for the past 7 days, suggest automations.

    Data:
    {trend_data}

    Provide suggestions in YAML format that Home Assistant can use directly.
    Automations should focus on:
    - Energy efficiency (lights, HVAC)
    - Security (locks, alarms)
    - User comfort (lighting, heating, reminders)
    - Predictive automations based on usage patterns
    """

def validate_automations(call: ServiceCall):
    headers = {
        "Authorization": f"Bearer {call.hass.data[DOMAIN]["ha_token"]}",
        "Content-Type": "application/json",
    }

    with open("automations.yaml", "r") as file:
        yaml_data = yaml.safe_load(file)

    url = f"{HA_URL}/api/config/core/check_config"
    response = requests.post(url, headers=headers)

    if response.status_code == 200:
        print("✅ Configuration check passed. Reloading automations...")
        reload_url = f"{HA_URL}/api/services/homeassistant/reload_core_config"
        requests.post(reload_url, headers=headers)
    else:
        print("Invalid configuration.")
