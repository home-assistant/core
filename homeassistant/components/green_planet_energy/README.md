# Green Planet Energy Integration

This integration provides real-time electricity pricing data from Green Planet Energy, a German renewable energy provider. It fetches hourly electricity prices and provides various sensors for energy optimization and monitoring.
It was written for the purpose to visualize the prices so that you can adpot your power consumption and shift it to cheaper hours.

## Features

- **29 Sensors Total**:
  - 24 hourly price sensors (`sensor.gpe_price_00` to `sensor.gpe_price_23`)
  - 5 statistical sensors for energy optimization and charting

### Statistical Sensors

1. **Current Price** (`sensor.gpe_current_price`)
   - Shows the electricity price for the current hour
   - Updates automatically based on the current time

2. **Highest Price Today** (`sensor.gpe_highest_price_today`)
   - Shows the highest electricity price of the day
   - Includes attributes: `highest_price_hour`, `time_slot`

3. **Lowest Price Day** (`sensor.gpe_lowest_price_day`)
   - Shows the lowest electricity price during day hours (06:00-18:00)
   - Includes attributes: `lowest_price_hour`, `time_slot`, `period`

4. **Lowest Price Night** (`sensor.gpe_lowest_price_night`)
   - Shows the lowest electricity price during night hours (18:00-06:00)
   - Includes attributes: `lowest_price_hour`, `time_slot`, `period`

5. **24h Price Chart Data** (`sensor.gpe_price_chart_24h`)
   - Provides the next 24 hours of price data for charting applications
   - Includes `chart_data` attribute with structured data for Apex Charts and other visualizations
   - Each data point contains: `hour`, `price`, `datetime`, `time_slot`, `day` (today/tomorrow)
   - Shows data from current hour forward for the next 24 hours

## Configuration

There is no configuration required.

## API Details

- **Data Source**: Green Planet Energy customer portal API
- **Update Frequency**: Hourly
- **Data Range**: Current day + next day (48 hours total)
- **Method**: JSON-RPC 2.0 API calls to `https://mein.green-planet-energy.de/p2`

## Sensor Attributes

### Hourly Sensors
Each hourly sensor (e.g., `sensor.gpe_price_00`) includes:
- `hour`: Hour of the day (0-23)
- `time_slot`: Time range (e.g., "00:00-01:00")
- `unit_of_measurement`: "€/kWh"

### Statistical Sensors
Statistical sensors include additional attributes:
- Time information for when the min/max price occurs
- Period information for day/night sensors
- Current hour for the current price sensor

## Dashboard Integration

### Apex Chart Example
```
type: custom:apexcharts-card
header:
  title: Electricity Prices - 24 Hours
  show: true
graph_span: 24h
span:
  start: day
now:
  show: true
  label: Now
series:
  - entity: sensor.gpe_price_chart_24h
    type: column
    attribute: chart_data
    data_generator: |
      return entity.attributes.chart_data.map((entry) => {
        return [new Date(entry.datetime).getTime(), entry.price];
      });
```

### Entity Card
```yaml
type: entities
title: "Green Planet Energy Prices"
entities:
  - entity: sensor.gpe_current_price
    name: "Current Price"
  - entity: sensor.gpe_highest_price_today
    name: "Highest Today"
  - entity: sensor.gpe_lowest_price_day
    name: "Lowest Day (06-18h)"
  - entity: sensor.gpe_lowest_price_night
    name: "Lowest Night (18-06h)"
  - entity: sensor.gpe_price_chart_24h
    name: "24h Chart Data"
```

### Apex Chart Configuration

For 24-hour price visualization using Apex Charts:

```yaml
type: custom:apexcharts-card
header:
  title: "Electricity Prices (Next 24h)"
  show: true
graph_span: 24h
now:
  show: true
  label: Now
yaxis:
  - min: 0
    max: ~0.6
    decimals: 3
series:
  - entity: sensor.gpe_price_chart_24h
    attribute: chart_data
    data_generator: |
      return entity.attributes.chart_data.map((entry) => {
        return [new Date(entry.datetime).getTime(), entry.price];
      });
    name: "Price"
    type: line
    stroke_width: 2
    color: "#ff6b6b"
```


## Troubleshooting

### Debug Logging
Add to your `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    homeassistant.components.green_planet_energy: debug
```

### Technical Details

### Sensor Naming Convention
- **Prefix**: All sensors use the `gpe_` prefix for easy identification
- **Hourly**: `gpe_price_XX` where XX is the hour (00-23)
- **Statistical**: `gpe_current_price`, `gpe_highest_price_today`, etc.
- **Chart Data**: `gpe_price_chart_24h` for visualization purposes

### Chart Data Structure
The `gpe_price_chart_24h` sensor provides structured data perfect for charts:
```json
{
  "chart_data": [
    {
      "hour": 12,
      "price": 0.32,
      "datetime": "2025-08-04T12:00:00+02:00",
      "time_slot": "12:00-13:00",
      "day": "today"
    },
    ...
  ],
  "data_points": 24,
  "last_updated": "2025-08-04T12:00:00+02:00"
}
```

### Data Processing
- API provides prices in €/kWh format
- Data is updated hourly to ensure current information
- Fallback mechanisms handle API unavailability

### Time Periods
- **Day Period**: 06:00 - 18:00 (12 hours)
- **Night Period**: 18:00 - 06:00 (12 hours, spans midnight)

## License

This integration is part of Home Assistant and follows the same Apache 2.0 license.
