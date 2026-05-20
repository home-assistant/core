# SRP Energy Integration

These notes are intended for developers of this integration to explain some of
the observed behavior of the SRP API. User facing information is present in the
Home Assistant documentation.

## Understanding SRP Usage API

The SRP usage API begins to release data for the previous day at midnight.
It appears SRP requires several hours to process data.
If you pull the data at midnight when it is released, it will likely be
missing the last several hours (they will have a value of 0).
In addition, the last non-zero hour _may_ be incomplete as they may have only
processed a subset of the time that is bundled in that hour. For example, it
may show as 0.5kwh at first and then a couple hours later as the rest of their
data is processed, the value could go up.

SRP seems to integrate data at a 4 hour cadence.
For example, at midnight when they finally allow you to access yesterday's data,
it typically has data for the first 20 hours, but the last 4 hours are all still
zero. After some time (around an hour in my observation), hour number 20 will
typically increase some (because at midnight it only had a partial hours worth
of data) and the remaining 4 hours will get populated. However, the last hour
will be a partial (just like the 20th hour was). Then approximately 4 hours
after those final hours are filled in, we see the last hour increase again to
its final value.

### Reported Costs

It has been observed that if you compare the calculated daily cost shown in home
assistant with the daily cost shown in SRP, it can vary by a few cents. This is
not something we can account for. I've manually done the math to confirm the
sum of a day's hourly data from the API is slightly different from the daily
data in the API and on the SRP website. My only guess is that when SRP
calculates the daily cost on their side, the hourly data goes out further than
2 digits and is therefore rounded differently than what we have access to in
our hourly data where the cost is either rounded or truncated to two decimal
places by the SRP servers (i.e. we never see more than two decimals).
