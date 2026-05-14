with base as (
    select * from {{ ref('stg_market_data') }}
),

symbol_stats as (
    select
        symbol,
        trade_date,
        count(*)                        as total_bars,
        min(low)                        as day_low,
        max(high)                       as day_high,
        round(avg(volume), 0)           as avg_volume,
        sum(volume)                     as total_volume,
        round(avg(pct_change), 4)       as avg_pct_change,
        round(avg(price_range), 4)      as avg_price_range,
        round(avg(typical_price), 4)    as avg_typical_price,
        min(timestamp)                  as market_open,
        max(timestamp)                  as market_close
    from base
    group by symbol, trade_date
)

select * from symbol_stats