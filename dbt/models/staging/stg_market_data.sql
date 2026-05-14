with source as (
    select * from {{ source('raw_market_data', 'market_data_raw') }}
),

staged as (
    select
        symbol,
        timestamp,
        open,
        high,
        low,
        close,
        volume,
        round(high - low, 4)                    as price_range,
        round((close - open) / open * 100, 4)   as pct_change,
        round((high + low + close) / 3, 4)      as typical_price,
        ingested_at,
        date(timestamp)                          as trade_date
    from source
    where timestamp is not null
      and volume > 0
)

select * from staged