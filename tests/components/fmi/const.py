"""Constants for FMI Tests."""

import datetime

import fmi_weather_client as fmi

MOCK_CURRENT = fmi.Weather(
    place="Dark side of Moon",
    lat=12.34567,
    lon=76.54321,
    data=fmi.models.WeatherData(
        time=datetime.datetime(2020, 10, 23, 6, 30, tzinfo=datetime.timezone.utc),
        temperature=fmi.models.Value(value=10.22, unit="°C"),
        dew_point=fmi.models.Value(value=8.98, unit="°C"),
        pressure=fmi.models.Value(value=992.56, unit="hPa"),
        humidity=fmi.models.Value(value=94.15, unit="%"),
        wind_direction=fmi.models.Value(value=239.0, unit="°"),
        wind_speed=fmi.models.Value(value=3.71, unit="m/s"),
        wind_u_component=fmi.models.Value(value=2.45, unit="m/s"),
        wind_v_component=fmi.models.Value(value=2.76, unit="m/s"),
        wind_max=fmi.models.Value(value=3.92, unit="m/s"),
        wind_gust=fmi.models.Value(value=9.39, unit="m/s"),
        symbol=fmi.models.Value(value=3.0, unit=""),
        cloud_cover=fmi.models.Value(value=99.09, unit="%"),
        cloud_low_cover=fmi.models.Value(value=85.8, unit="%"),
        cloud_mid_cover=fmi.models.Value(value=45.0, unit="%"),
        cloud_high_cover=fmi.models.Value(value=94.9, unit="%"),
        precipitation_amount=fmi.models.Value(value=0.0, unit="mm/h"),
        radiation_short_wave_acc=fmi.models.Value(value=19606.75, unit="J/m²"),
        radiation_short_wave_surface_net_acc=fmi.models.Value(
            value=17733.67, unit="J/m²"
        ),
        radiation_long_wave_acc=fmi.models.Value(value=8661770.0, unit="J/m²"),
        radiation_long_wave_surface_net_acc=fmi.models.Value(
            value=-348419.88, unit="J/m²"
        ),
        radiation_short_wave_diff_surface_acc=fmi.models.Value(
            value=20100.51, unit="J/m²"
        ),
        geopotential_height=fmi.models.Value(value=43.68, unit="m"),
        land_sea_mask=fmi.models.Value(value=0.95, unit=""),
    ),
)

MOCK_FORECAST = fmi.models.Forecast(
    place="Dark side of Moon",
    lat=12.34567,
    lon=76.54321,
    forecasts=[
        fmi.models.WeatherData(
            time=datetime.datetime(2020, 10, 23, 12, 0, tzinfo=datetime.timezone.utc),
            temperature=fmi.models.Value(value=7.44, unit="°C"),
            dew_point=fmi.models.Value(value=6.51, unit="°C"),
            pressure=fmi.models.Value(value=995.68, unit="hPa"),
            humidity=fmi.models.Value(value=95.46, unit="%"),
            wind_direction=fmi.models.Value(value=309.0, unit="°"),
            wind_speed=fmi.models.Value(value=3.92, unit="m/s"),
            wind_u_component=fmi.models.Value(value=3.77, unit="m/s"),
            wind_v_component=fmi.models.Value(value=-1.16, unit="m/s"),
            wind_max=fmi.models.Value(value=4.01, unit="m/s"),
            wind_gust=fmi.models.Value(value=9.95, unit="m/s"),
            symbol=fmi.models.Value(value=31.0, unit=""),
            cloud_cover=fmi.models.Value(value=93.33, unit="%"),
            cloud_low_cover=fmi.models.Value(value=69.9, unit="%"),
            cloud_mid_cover=fmi.models.Value(value=0.0, unit="%"),
            cloud_high_cover=fmi.models.Value(value=0.0, unit="%"),
            precipitation_amount=fmi.models.Value(value=0.2, unit="mm/h"),
            radiation_short_wave_acc=fmi.models.Value(value=1475935.63, unit="J/m²"),
            radiation_short_wave_surface_net_acc=fmi.models.Value(
                value=1306123.25, unit="J/m²"
            ),
            radiation_long_wave_acc=fmi.models.Value(value=15466976.0, unit="J/m²"),
            radiation_long_wave_surface_net_acc=fmi.models.Value(
                value=-1008584.19, unit="J/m²"
            ),
            radiation_short_wave_diff_surface_acc=fmi.models.Value(
                value=1050999.88, unit="J/m²"
            ),
            geopotential_height=fmi.models.Value(value=43.68, unit="m"),
            land_sea_mask=fmi.models.Value(value=0.95, unit=""),
        ),
        fmi.models.WeatherData(
            time=datetime.datetime(2020, 10, 24, 0, 0, tzinfo=datetime.timezone.utc),
            temperature=fmi.models.Value(value=-1.16, unit="°C"),
            dew_point=fmi.models.Value(value=-1.75, unit="°C"),
            pressure=fmi.models.Value(value=1005.67, unit="hPa"),
            humidity=fmi.models.Value(value=96.93, unit="%"),
            wind_direction=fmi.models.Value(value=258.0, unit="°"),
            wind_speed=fmi.models.Value(value=1.53, unit="m/s"),
            wind_u_component=fmi.models.Value(value=1.32, unit="m/s"),
            wind_v_component=fmi.models.Value(value=0.8, unit="m/s"),
            wind_max=fmi.models.Value(value=3.07, unit="m/s"),
            wind_gust=fmi.models.Value(value=3.78, unit="m/s"),
            symbol=fmi.models.Value(value=1.0, unit=""),
            cloud_cover=fmi.models.Value(value=8.03, unit="%"),
            cloud_low_cover=fmi.models.Value(value=5.5, unit="%"),
            cloud_mid_cover=fmi.models.Value(value=0.0, unit="%"),
            cloud_high_cover=fmi.models.Value(value=0.0, unit="%"),
            precipitation_amount=fmi.models.Value(value=0.0, unit="mm/h"),
            radiation_short_wave_acc=fmi.models.Value(value=1843989.38, unit="J/m²"),
            radiation_short_wave_surface_net_acc=fmi.models.Value(
                value=1627175.63, unit="J/m²"
            ),
            radiation_long_wave_acc=fmi.models.Value(value=27052616.0, unit="J/m²"),
            radiation_long_wave_surface_net_acc=fmi.models.Value(
                value=-4287095.5, unit="J/m²"
            ),
            radiation_short_wave_diff_surface_acc=fmi.models.Value(
                value=1312482.63, unit="J/m²"
            ),
            geopotential_height=fmi.models.Value(value=43.68, unit="m"),
            land_sea_mask=fmi.models.Value(value=0.95, unit=""),
        ),
        fmi.models.WeatherData(
            time=datetime.datetime(2020, 10, 24, 12, 0, tzinfo=datetime.timezone.utc),
            temperature=fmi.models.Value(value=6.73, unit="°C"),
            dew_point=fmi.models.Value(value=-0.67, unit="°C"),
            pressure=fmi.models.Value(value=1005.96, unit="hPa"),
            humidity=fmi.models.Value(value=68.51, unit="%"),
            wind_direction=fmi.models.Value(value=245.0, unit="°"),
            wind_speed=fmi.models.Value(value=1.0, unit="m/s"),
            wind_u_component=fmi.models.Value(value=0.69, unit="m/s"),
            wind_v_component=fmi.models.Value(value=0.71, unit="m/s"),
            wind_max=fmi.models.Value(value=1.11, unit="m/s"),
            wind_gust=fmi.models.Value(value=3.63, unit="m/s"),
            symbol=fmi.models.Value(value=3.0, unit=""),
            cloud_cover=fmi.models.Value(value=99.38, unit="%"),
            cloud_low_cover=fmi.models.Value(value=74.9, unit="%"),
            cloud_mid_cover=fmi.models.Value(value=93.8, unit="%"),
            cloud_high_cover=fmi.models.Value(value=92.1, unit="%"),
            precipitation_amount=fmi.models.Value(value=0.0, unit="mm/h"),
            radiation_short_wave_acc=fmi.models.Value(value=4667982.5, unit="J/m²"),
            radiation_short_wave_surface_net_acc=fmi.models.Value(
                value=4118623.75, unit="J/m²"
            ),
            radiation_long_wave_acc=fmi.models.Value(value=39463816.0, unit="J/m²"),
            radiation_long_wave_surface_net_acc=fmi.models.Value(
                value=-6645959.5, unit="J/m²"
            ),
            radiation_short_wave_diff_surface_acc=fmi.models.Value(
                value=3905288.0, unit="J/m²"
            ),
            geopotential_height=fmi.models.Value(value=43.68, unit="m"),
            land_sea_mask=fmi.models.Value(value=0.95, unit=""),
        ),
        fmi.models.WeatherData(
            time=datetime.datetime(2020, 10, 25, 0, 0, tzinfo=datetime.timezone.utc),
            temperature=fmi.models.Value(value=5.14, unit="°C"),
            dew_point=fmi.models.Value(value=4.73, unit="°C"),
            pressure=fmi.models.Value(value=1003.7, unit="hPa"),
            humidity=fmi.models.Value(value=97.94, unit="%"),
            wind_direction=fmi.models.Value(value=31.0, unit="°"),
            wind_speed=fmi.models.Value(value=2.47, unit="m/s"),
            wind_u_component=fmi.models.Value(value=-0.42, unit="m/s"),
            wind_v_component=fmi.models.Value(value=-2.4, unit="m/s"),
            wind_max=fmi.models.Value(value=2.59, unit="m/s"),
            wind_gust=fmi.models.Value(value=6.24, unit="m/s"),
            symbol=fmi.models.Value(value=3.0, unit=""),
            cloud_cover=fmi.models.Value(value=100.0, unit="%"),
            cloud_low_cover=fmi.models.Value(value=99.9, unit="%"),
            cloud_mid_cover=fmi.models.Value(value=0.0, unit="%"),
            cloud_high_cover=fmi.models.Value(value=0.0, unit="%"),
            precipitation_amount=fmi.models.Value(value=0.0, unit="mm/h"),
            radiation_short_wave_acc=fmi.models.Value(value=5123953.0, unit="J/m²"),
            radiation_short_wave_surface_net_acc=fmi.models.Value(
                value=4522412.0, unit="J/m²"
            ),
            radiation_long_wave_acc=fmi.models.Value(value=54374984.0, unit="J/m²"),
            radiation_long_wave_surface_net_acc=fmi.models.Value(
                value=-7264103.0, unit="J/m²"
            ),
            radiation_short_wave_diff_surface_acc=fmi.models.Value(
                value=4355270.5, unit="J/m²"
            ),
            geopotential_height=fmi.models.Value(value=43.68, unit="m"),
            land_sea_mask=fmi.models.Value(value=0.95, unit=""),
        ),
    ],
)
