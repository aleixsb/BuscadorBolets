import datetime as dt
from collections import defaultdict

from meteocat.aggregations import aggregate_precipitation


def test_weekly_monthly_yearly_aggregation():
    start = dt.date(2024, 8, 1)
    days = [
        {"date": (start + dt.timedelta(days=i)).isoformat(), "value": i % 5}
        for i in range(62)
    ]

    result = aggregate_precipitation(days)

    assert set(result.keys()) == {"weekly", "monthly", "yearly"}

    expected_monthly: dict[str, float] = defaultdict(float)
    expected_yearly: dict[str, float] = defaultdict(float)
    for entry in days:
        date = dt.date.fromisoformat(entry["date"])
        month_key = f"{date.year}-{date.month:02d}"
        expected_monthly[month_key] += entry["value"]
        expected_yearly[str(date.year)] += entry["value"]

    monthly = {item["period"]: item["value"] for item in result["monthly"]}
    for key, value in expected_monthly.items():
        assert monthly[key] == round(value, 2)

    yearly = {item["period"]: item["value"] for item in result["yearly"]}
    for key, value in expected_yearly.items():
        assert yearly[key] == round(value, 2)

    weekly_periods = {item["period"]: item["value"] for item in result["weekly"]}
    assert weekly_periods["2024-W31"] > 0
    assert weekly_periods["2024-W36"] > 0
