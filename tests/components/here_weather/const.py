"""Constants for here_weather tests."""
import herepy

daily_forecasts_json = {
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

daily_forecasts_response = herepy.DestinationWeatherResponse.new_from_jsondict(
    daily_forecasts_json, param_defaults={"dailyForecasts": None}
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
