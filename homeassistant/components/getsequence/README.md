# Sequence Integration for Home Assistant

This integration connects Home Assistant to your Sequence financial orchestration platform, allowing you to monitor your pods, account balances, financial data, and cash flow over time.

## Features

### Core Balance Tracking
- **Pod Sensors**: Individual sensors for each pod showing current balance
- **Net Balance Sensor**: Aggregated view of total balance across all accounts
- **Account Type Totals**: Separate totals for pods, income sources, external accounts
- **Manual Categorization**: Configure external accounts as liabilities or investments

### Cash Flow Utility Meters (Disabled by Default)
- **Daily/Weekly/Monthly/Yearly Tracking**: Track positive cash flow over different time periods
- **Individual Device Meters**: Separate utility meters for each pod, income source, and external account
- **Aggregate Meters**: Total cash flow tracking across account types
- **Incremental Tracking**: Uses `TOTAL_INCREASING` state class for proper utility meter behavior

### Configuration & Management
- **Options Flow**: Configure external account categorization after setup
- **Real-time Updates**: Data refreshed every 5 minutes
- **Error Handling**: Proper error handling and recovery
- **Reauthentication**: Support for token renewal

## Setup

1. **Get your API Access Token**:
   - Log in to your Sequence dashboard
   - Navigate to Settings → Enable Remote API
   - Generate a new API access token

2. **Add the Integration**:
   - Go to Settings → Devices & Services → Add Integration
   - Search for "Sequence" and select it
   - Enter your API access token
   - Click "Submit"

## Entities Created

The integration creates the following entities:

### Balance Sensors (Always Enabled)
- `sensor.sequence_net_balance` - Total balance across all accounts
- `sensor.sequence_pods_total` - Total balance across pods only
- `sensor.sequence_liability_total` - Total of manually categorized liability accounts
- `sensor.sequence_investment_total` - Total of manually categorized investment accounts
- `sensor.sequence_income_source_total` - Total balance across income sources
- `sensor.sequence_external_total` - Total of uncategorized external accounts
- `sensor.sequence_data_age` - Age of the last successful data fetch

### Individual Account Sensors
- `sensor.sequence_[pod_name]` - Balance for each individual pod
- `sensor.sequence_[income_source_name]` - Balance for each income source
- `sensor.sequence_[external_account_name]` - Balance for each external account
- Attributes include account ID, name, type, and any balance errors

### Cash Flow Utility Meters (Disabled by Default)

These sensors track positive cash flow (increases) over time and are disabled by default to avoid clutter. Enable them individually as needed.

#### Aggregate Cash Flow Sensors
- `sensor.sequence_cash_flow_daily` - Daily positive cash flow across all accounts
- `sensor.sequence_cash_flow_weekly` - Weekly positive cash flow across all accounts
- `sensor.sequence_cash_flow_monthly` - Monthly positive cash flow across all accounts
- `sensor.sequence_cash_flow_yearly` - Yearly positive cash flow across all accounts

#### Income Source Cash Flow Sensors
- `sensor.sequence_income_source_cash_flow_daily` - Daily income source cash flow total
- `sensor.sequence_income_source_cash_flow_weekly` - Weekly income source cash flow total
- `sensor.sequence_income_source_cash_flow_monthly` - Monthly income source cash flow total
- `sensor.sequence_income_source_cash_flow_yearly` - Yearly income source cash flow total

#### Pod Cash Flow Sensors
- `sensor.sequence_pods_cash_flow_daily` - Daily pods cash flow total
- `sensor.sequence_pods_cash_flow_weekly` - Weekly pods cash flow total
- `sensor.sequence_pods_cash_flow_monthly` - Monthly pods cash flow total
- `sensor.sequence_pods_cash_flow_yearly` - Yearly pods cash flow total

#### External Account Cash Flow Sensors
- `sensor.sequence_external_cash_flow_daily` - Daily external cash flow total
- `sensor.sequence_external_cash_flow_weekly` - Weekly external cash flow total
- `sensor.sequence_external_cash_flow_monthly` - Monthly external cash flow total
- `sensor.sequence_external_cash_flow_yearly` - Yearly external cash flow total

#### Individual Account Cash Flow Sensors
Each income source and external account gets its own set of utility meters:
- `sensor.sequence_[account_name]_cash_flow_daily`
- `sensor.sequence_[account_name]_cash_flow_weekly`
- `sensor.sequence_[account_name]_cash_flow_monthly`
- `sensor.sequence_[account_name]_cash_flow_yearly`

### Device Organization
- **Main Account Device**: Contains aggregate sensors and totals
- **Individual Account Devices**: Each pod, income source, and external account becomes its own device
- **Proper Grouping**: Related sensors are grouped under their respective devices

## Configuration

### Initial Setup
The integration is configured through the UI. The only required parameter is your Sequence API access token.

### Options Configuration
After setup, you can configure additional options:

1. **Navigate to Integration Settings**:
   - Go to Settings → Devices & Services → Sequence
   - Click "Configure" on the Sequence integration

2. **External Account Categorization**:
   - Select external accounts to categorize as "Liability" or "Investment"
   - This affects which accounts are included in the respective total sensors
   - Uncategorized accounts appear in the "External Total" sensor

### Utility Meter Configuration
The integration creates many cash flow utility meters that are disabled by default. To use them:

1. **Navigate to Entities**:
   - Go to Settings → Devices & Services → Entities
   - Filter by "getsequence" domain

2. **Enable Desired Sensors**:
   - Find cash flow sensors you want to track
   - Click the entity to open details
   - Toggle "Enabled" to activate the sensor

3. **Recommended Utility Meters**:
   - Daily sensors for short-term cash flow monitoring
   - Monthly/Yearly sensors for longer-term financial planning
   - Individual account sensors for detailed tracking

### Update Frequency
- Data is refreshed every 5 minutes by default
- Cash flow calculations are updated with each data refresh
- Utility meters track cumulative positive changes over time

## API Limitations

- **Cash Flow Calculation**: Cash flow is calculated from balance changes, not transaction history
- **Reset Behavior**: Utility meters reset their accumulation if the integration is restarted
- **Real-time Updates**: Polling-based updates only (no webhook support documented)
- **Account Categorization**: Manual configuration required for external account categorization

## Use Cases

### Personal Finance Tracking
- Monitor overall financial health with net balance sensor
- Track income flow with income source utility meters
- Monitor spending patterns with pod cash flow sensors
- Categorize external accounts for investment/liability tracking

### Automation Ideas
- **Low Balance Alerts**: Trigger notifications when account balances drop below thresholds
- **Cash Flow Monitoring**: Alert on unusual cash flow patterns
- **Investment Tracking**: Monitor investment account performance over time
- **Budget Management**: Track monthly cash flow against budget targets

### Dashboard Integration
- Create financial dashboard cards with balance sensors
- Use utility meter data for cash flow charts
- Group related accounts using device organization
- Display trends using historical utility meter data

## Troubleshooting

1. **Invalid Auth Error**: Check that your API access token is correct and hasn't expired
2. **Cannot Connect Error**: Verify internet connectivity and that the Sequence API is accessible
3. **Missing Pods**: Ensure your account has pods configured in Sequence

## Development

This integration is built using:
- Async HTTP client with proper error handling
- DataUpdateCoordinator for efficient API polling
- Proper Home Assistant entity patterns
- Comprehensive test coverage

For development setup:
1. Clone the Home Assistant core repository
2. Copy the integration files to `homeassistant/components/getsequence/`
3. Run tests with `python -m pytest tests/components/getsequence/`

## License

This integration follows Home Assistant's contribution guidelines and licensing.