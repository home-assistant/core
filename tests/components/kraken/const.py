"""Constants for kraken tests."""
import pandas

TRADEABLE_ASSET_PAIR_RESPONSE = pandas.DataFrame(
    {"wsname": ["XBT/USD"]}, columns=["wsname"], index=["XXBTZUSD"]
)
TICKER_INFORMATION_RESPONSE = pandas.DataFrame(
    {
        "a": [[0.000349400, 15949, 15949.000]],
        "b": [[0.000348400, 20792, 20792.000]],
        "c": [[0.000347800, 2809.36384377]],
        "h": [[0.000351600, 0.000352100]],
        "l": [[0.000344600, 0.000344600]],
        "o": [0.000351300],
        "p": [[0.000348573, 0.000344881]],
        "t": [[82, 128]],
        "v": [[146300.24906838, 253478.04715403]],
    },
    columns=["a", "b", "c", "h", "l", "o", "p", "t", "v"],
    index=["XXBTZUSD"],
)
