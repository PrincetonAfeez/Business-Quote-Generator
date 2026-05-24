# ADR 1: Decimal For Money

Money fields use `DecimalField` and calculations use `decimal.Decimal` because binary floats cannot represent many decimal amounts exactly. A simple value such as `0.1 + 0.2` can produce an imprecise binary result, which is unacceptable for quotes and tax totals.

All display values are quantized to two places with `ROUND_HALF_UP`.
