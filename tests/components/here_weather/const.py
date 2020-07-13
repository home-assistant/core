"""Constants for here_weather tests."""
import herepy

daily_simple_forecasts_json = {
    "dailyForecasts": {
        "forecastLocation": {
            "forecast": [
                {
                    "daylight": "D",
                    "description": "Overcast. Chilly.",
                    "skyInfo": "18",
                    "skyDescription": "Overcast",
                    "temperatureDesc": "Chilly",
                    "comfort": "-0.55",
                    "highTemperature": "4.00",
                    "lowTemperature": "-1.80",
                    "humidity": "80",
                    "dewPoint": "-0.40",
                    "precipitationProbability": "53",
                    "precipitationDesc": "",
                    "rainFall": "*",
                    "snowFall": "1.42",
                    "airInfo": "*",
                    "airDescription": "",
                    "windSpeed": "12.03",
                    "windDirection": "290",
                    "windDesc": "West",
                    "windDescShort": "W",
                    "beaufortScale": "3",
                    "beaufortDescription": "Gentle breeze",
                    "uvIndex": "0",
                    "uvDesc": "Minimal",
                    "barometerPressure": "1014.29",
                    "icon": "7",
                    "iconName": "cloudy",
                    "iconLink": "https://weather.cit.api.here.com/static/weather/icon/17.png",
                    "dayOfWeek": "3",
                    "weekday": "Tuesday",
                    "utcTime": "2019-11-19T00:00:00.000-05:00",
                }
            ],
            "country": "United States",
            "state": "New York",
            "city": "New York",
            "latitude": 43.00035,
            "longitude": -75.4999,
            "distance": 0.00,
            "timezone": -5,
        }
    },
    "feedCreation": "2019-11-19T23:01:26.632Z",
    "metric": True,
}

daily_simple_forecasts_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    daily_simple_forecasts_json, param_defaults={"dailyForecasts": None}
)

astronomy_json = {
    "astronomy": {
        "astronomy": [
            {
                "sunrise": "6:55AM",
                "sunset": "6:33PM",
                "moonrise": "1:27PM",
                "moonset": "10:58PM",
                "moonPhase": 0.328,
                "moonPhaseDesc": "Waxing crescent",
                "iconName": "cw_waxing_crescent",
                "city": "Edgewater",
                "latitude": 40.82,
                "longitude": -73.97,
                "utcTime": "2019-10-04T00:00:00.000-04:00",
            }
        ],
        "country": "United States",
        "state": "New York",
        "city": "New York",
        "latitude": 40.79962,
        "longitude": -73.970314,
        "timezone": -5,
    },
    "feedCreation": "2019-10-04T14:22:46.164Z",
    "metric": True,
}

astronomy_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    astronomy_json, param_defaults={"astronomy": None}
)

hourly_json = {
    "hourlyForecasts": {
        "forecastLocation": {
            "forecast": [
                {
                    "daylight": "D",
                    "description": "Overcast. Chilly.",
                    "skyInfo": "18",
                    "skyDescription": "Overcast",
                    "temperature": "4.00",
                    "temperatureDesc": "Chilly",
                    "comfort": "0.67",
                    "humidity": "74",
                    "dewPoint": "-0.30",
                    "precipitationProbability": "5",
                    "precipitationDesc": "",
                    "rainFall": "*",
                    "snowFall": "*",
                    "airInfo": "*",
                    "airDescription": "",
                    "windSpeed": "14.04",
                    "windDirection": "287",
                    "windDesc": "West",
                    "windDescShort": "W",
                    "visibility": "11.31",
                    "icon": "7",
                    "iconName": "cloudy",
                    "iconLink": "https://weather.cit.api.here.com/static/weather/icon/17.png",
                    "dayOfWeek": "3",
                    "weekday": "Tuesday",
                    "utcTime": "2019-11-19T13:00:00.000-05:00",
                    "localTime": "1311192019",
                    "localTimeFormat": "HHMMddyyyy",
                }
            ],
            "country": "United States",
            "state": "New York",
            "city": "New York",
            "latitude": 43.00035,
            "longitude": -75.4999,
            "distance": 0.00,
            "timezone": -5,
        }
    },
    "feedCreation": "2019-11-19T23:06:04.631Z",
    "metric": True,
}

hourly_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    hourly_json, param_defaults={"hourlyForecasts": None}
)

observation_json = {
    "observations": {
        "location": [
            {
                "observation": [
                    {
                        "daylight": "D",
                        "description": "Overcast. Cool.",
                        "skyInfo": "18",
                        "skyDescription": "Overcast",
                        "temperature": "46.00",
                        "temperatureDesc": "Cool",
                        "comfort": "42.39",
                        "highTemperature": "50.72",
                        "lowTemperature": "39.74",
                        "humidity": "63",
                        "dewPoint": "34.00",
                        "precipitation1H": "*",
                        "precipitation3H": "*",
                        "precipitation6H": "*",
                        "precipitation12H": "*",
                        "precipitation24H": "*",
                        "precipitationDesc": "",
                        "airInfo": "*",
                        "airDescription": "",
                        "windSpeed": "6.89",
                        "windDirection": "0",
                        "windDesc": "North",
                        "windDescShort": "N",
                        "barometerPressure": "29.80",
                        "barometerTrend": "Rising",
                        "visibility": "10.00",
                        "snowCover": "*",
                        "icon": "7",
                        "iconName": "cloudy",
                        "iconLink": "https://weather.cit.api.here.com/static/weather/icon/17.png",
                        "ageMinutes": "46",
                        "activeAlerts": "6",
                        "country": "United States",
                        "state": "New York",
                        "city": "New York",
                        "latitude": 40.7996,
                        "longitude": -73.9703,
                        "distance": 1.43,
                        "elevation": 0.00,
                        "utcTime": "2019-11-19T15:51:00.000-05:00",
                    }
                ],
                "country": "United States",
                "state": "New York",
                "city": "New York",
                "latitude": 40.79962,
                "longitude": -73.970314,
                "distance": 0.00,
                "timezone": -5,
            }
        ]
    },
    "feedCreation": "2019-11-19T21:37:57.279Z",
    "metric": False,
}

observation_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    observation_json, param_defaults={"observations": None}
)

daily_json = {
    "forecasts": {
        "forecastLocation": {
            "forecast": [
                {
                    "daylight": "D",
                    "daySegment": "Afternoon",
                    "description": "Overcast. Chilly.",
                    "skyInfo": "18",
                    "skyDescription": "Overcast",
                    "temperature": "4.00",
                    "temperatureDesc": "Chilly",
                    "comfort": "0.86",
                    "humidity": "73",
                    "dewPoint": "-0.40",
                    "precipitationProbability": "9",
                    "precipitationDesc": "",
                    "rainFall": "*",
                    "snowFall": "*",
                    "airInfo": "*",
                    "airDescription": "",
                    "windSpeed": "12.96",
                    "windDirection": "294",
                    "windDesc": "Northwest",
                    "windDescShort": "NW",
                    "beaufortScale": "3",
                    "beaufortDescription": "Gentle breeze",
                    "visibility": "11.38",
                    "icon": "7",
                    "iconName": "cloudy",
                    "iconLink": "https://weather.cit.api.here.com/static/weather/icon/17.png",
                    "dayOfWeek": "3",
                    "weekday": "Tuesday",
                    "utcTime": "2019-11-19T12:00:00.000-05:00",
                }
            ],
            "country": "United States",
            "state": "New York",
            "city": "New York",
            "latitude": 43.00035,
            "longitude": -75.4999,
            "distance": 0.00,
            "timezone": -5,
        }
    },
    "feedCreation": "2019-11-19T22:49:09.348Z",
    "metric": True,
}

daily_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    daily_json, param_defaults={"forecasts": None}
)
