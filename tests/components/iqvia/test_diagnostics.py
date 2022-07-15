"""Test IQVIA diagnostics."""
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_iqvia):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "title": "Mock Title",
            "data": {
                "zip_code": "12345",
            },
        },
        "data": {
            "allergy_average_forecasted": {
                "Type": "pollen",
                "ForecastDate": "2018-06-12T00:00:00-04:00",
                "Location": {
                    "ZIP": "12345",
                    "City": "SCHENECTADY",
                    "State": "NY",
                    "periods": [
                        {"Period": "2018-06-12T13:47:12.897", "Index": 6.6},
                        {"Period": "2018-06-13T13:47:12.897", "Index": 6.3},
                        {"Period": "2018-06-14T13:47:12.897", "Index": 7.6},
                        {"Period": "2018-06-15T13:47:12.897", "Index": 7.6},
                        {"Period": "2018-06-16T13:47:12.897", "Index": 7.3},
                    ],
                    "DisplayLocation": "Schenectady, NY",
                },
            },
            "allergy_index": {
                "Type": "pollen",
                "ForecastDate": "2018-06-12T00:00:00-04:00",
                "Location": {
                    "ZIP": "12345",
                    "City": "SCHENECTADY",
                    "State": "NY",
                    "periods": [
                        {
                            "Triggers": [
                                {
                                    "LGID": 272,
                                    "Name": "Juniper",
                                    "Genus": "Juniperus",
                                    "PlantType": "Tree",
                                },
                                {
                                    "LGID": 346,
                                    "Name": "Grasses",
                                    "Genus": "Grasses",
                                    "PlantType": "Grass",
                                },
                                {
                                    "LGID": 63,
                                    "Name": "Chenopods",
                                    "Genus": "Chenopods",
                                    "PlantType": "Ragweed",
                                },
                            ],
                            "Period": "0001-01-01T00:00:00",
                            "Type": "Yesterday",
                            "Index": 7.2,
                        },
                        {
                            "Triggers": [
                                {
                                    "LGID": 272,
                                    "Name": "Juniper",
                                    "Genus": "Juniperus",
                                    "PlantType": "Tree",
                                },
                                {
                                    "LGID": 346,
                                    "Name": "Grasses",
                                    "Genus": "Grasses",
                                    "PlantType": "Grass",
                                },
                                {
                                    "LGID": 63,
                                    "Name": "Chenopods",
                                    "Genus": "Chenopods",
                                    "PlantType": "Ragweed",
                                },
                            ],
                            "Period": "0001-01-01T00:00:00",
                            "Type": "Today",
                            "Index": 6.6,
                        },
                        {
                            "Triggers": [
                                {
                                    "LGID": 272,
                                    "Name": "Juniper",
                                    "Genus": "Juniperus",
                                    "PlantType": "Tree",
                                },
                                {
                                    "LGID": 346,
                                    "Name": "Grasses",
                                    "Genus": "Grasses",
                                    "PlantType": "Grass",
                                },
                                {
                                    "LGID": 63,
                                    "Name": "Chenopods",
                                    "Genus": "Chenopods",
                                    "PlantType": "Ragweed",
                                },
                            ],
                            "Period": "0001-01-01T00:00:00",
                            "Type": "Tomorrow",
                            "Index": 6.3,
                        },
                    ],
                    "DisplayLocation": "Schenectady, NY",
                },
            },
            "allergy_outlook": {
                "Market": "SCHENECTADY, CO",
                "ZIP": "12345",
                "TrendID": 4,
                "Trend": "subsiding",
                "Outlook": "The amount of pollen in the air for Wednesday...",
                "Season": "Tree",
            },
            "asthma_average_forecasted": {
                "Type": "asthma",
                "ForecastDate": "2018-10-28T00:00:00-04:00",
                "Location": {
                    "ZIP": "12345",
                    "City": "SCHENECTADY",
                    "State": "NY",
                    "periods": [
                        {
                            "Period": "2018-10-28T05:45:01.45",
                            "Index": 4.5,
                            "Idx": "4.5",
                        },
                        {
                            "Period": "2018-10-29T05:45:01.45",
                            "Index": 4.7,
                            "Idx": "4.7",
                        },
                        {"Period": "2018-10-30T05:45:01.45", "Index": 5, "Idx": "5.0"},
                        {
                            "Period": "2018-10-31T05:45:01.45",
                            "Index": 5.2,
                            "Idx": "5.2",
                        },
                        {
                            "Period": "2018-11-01T05:45:01.45",
                            "Index": 5.5,
                            "Idx": "5.5",
                        },
                    ],
                    "DisplayLocation": "Schenectady, NY",
                },
            },
            "asthma_index": {
                "Type": "asthma",
                "ForecastDate": "2018-10-29T00:00:00-04:00",
                "Location": {
                    "ZIP": "12345",
                    "City": "SCHENECTADY",
                    "State": "NY",
                    "periods": [
                        {
                            "Triggers": [
                                {
                                    "LGID": 1,
                                    "Name": "OZONE",
                                    "PPM": 42,
                                    "Description": "Ozone (O3) is a odorless, colorless ....",
                                },
                                {
                                    "LGID": 1,
                                    "Name": "PM2.5",
                                    "PPM": 30,
                                    "Description": "Fine particles (PM2.5) are 2.5 ...",
                                },
                                {
                                    "LGID": 1,
                                    "Name": "PM10",
                                    "PPM": 19,
                                    "Description": "Coarse dust particles (PM10) are 2.5 ...",
                                },
                            ],
                            "Period": "0001-01-01T00:00:00",
                            "Type": "Yesterday",
                            "Index": 4.1,
                            "Idx": "4.1",
                        },
                        {
                            "Triggers": [
                                {
                                    "LGID": 3,
                                    "Name": "PM2.5",
                                    "PPM": 105,
                                    "Description": "Fine particles (PM2.5) are 2.5 ...",
                                },
                                {
                                    "LGID": 2,
                                    "Name": "PM10",
                                    "PPM": 65,
                                    "Description": "Coarse dust particles (PM10) are 2.5 ...",
                                },
                                {
                                    "LGID": 1,
                                    "Name": "OZONE",
                                    "PPM": 42,
                                    "Description": "Ozone (O3) is a odorless, colorless ...",
                                },
                            ],
                            "Period": "0001-01-01T00:00:00",
                            "Type": "Today",
                            "Index": 4.5,
                            "Idx": "4.5",
                        },
                        {
                            "Triggers": [],
                            "Period": "0001-01-01T00:00:00",
                            "Type": "Tomorrow",
                            "Index": 4.6,
                            "Idx": "4.6",
                        },
                    ],
                    "DisplayLocation": "Schenectady, NY",
                },
            },
            "disease_average_forecasted": {
                "Type": "cold",
                "ForecastDate": "2018-06-12T00:00:00-04:00",
                "Location": {
                    "ZIP": "12345",
                    "City": "SCHENECTADY",
                    "State": "NY",
                    "periods": [
                        {"Period": "2018-06-12T05:13:51.817", "Index": 2.4},
                        {"Period": "2018-06-13T05:13:51.817", "Index": 2.5},
                        {"Period": "2018-06-14T05:13:51.817", "Index": 2.5},
                        {"Period": "2018-06-15T05:13:51.817", "Index": 2.5},
                    ],
                    "DisplayLocation": "Schenectady, NY",
                },
            },
            "disease_index": {
                "ForecastDate": "2019-04-07T00:00:00-04:00",
                "Location": {
                    "City": "SCHENECTADY",
                    "DisplayLocation": "Schenectady, NY",
                    "State": "NY",
                    "ZIP": "12345",
                    "periods": [
                        {
                            "Idx": "6.8",
                            "Index": 6.8,
                            "Period": "2019-04-06T00:00:00",
                            "Triggers": [
                                {
                                    "Description": "Influenza",
                                    "Idx": "3.1",
                                    "Index": 3.1,
                                    "Name": "Flu",
                                },
                                {
                                    "Description": "High Fever",
                                    "Idx": "6.2",
                                    "Index": 6.2,
                                    "Name": "Fever",
                                },
                                {
                                    "Description": "Strep & Sore throat",
                                    "Idx": "5.2",
                                    "Index": 5.2,
                                    "Name": "Strep",
                                },
                                {
                                    "Description": "Cough",
                                    "Idx": "7.8",
                                    "Index": 7.8,
                                    "Name": "Cough",
                                },
                            ],
                            "Type": "Yesterday",
                        },
                        {
                            "Idx": "6.7",
                            "Index": 6.7,
                            "Period": "2019-04-07T03:52:58",
                            "Triggers": [
                                {
                                    "Description": "Influenza",
                                    "Idx": "3.1",
                                    "Index": 3.1,
                                    "Name": "Flu",
                                },
                                {
                                    "Description": "High Fever",
                                    "Idx": "5.9",
                                    "Index": 5.9,
                                    "Name": "Fever",
                                },
                                {
                                    "Description": "Strep & Sore throat",
                                    "Idx": "5.1",
                                    "Index": 5.1,
                                    "Name": "Strep",
                                },
                                {
                                    "Description": "Cough",
                                    "Idx": "7.7",
                                    "Index": 7.7,
                                    "Name": "Cough",
                                },
                            ],
                            "Type": "Today",
                        },
                    ],
                },
                "Type": "cold",
            },
        },
    }
