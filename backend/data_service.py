
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DATA = ROOT / "data" / "normalized" / "sleep_sessions.csv"
DEMO_DATA = ROOT / "data" / "demo" / "synthetic_sleep_sessions.csv"


def resolve_sleep_data_path():
    """Prefer local private data and fall back to the repository-safe demo fixture."""
    if PRIVATE_DATA.exists():
        return PRIVATE_DATA
    if DEMO_DATA.exists():
        return DEMO_DATA
    raise FileNotFoundError(
        "未找到睡眠数据。请提供data/normalized/sleep_sessions.csv，"
        "或保留data/demo/synthetic_sleep_sessions.csv。"
    )

METRIC_METADATA = {
    "total_sleep_duration": {"label": "总睡眠时长", "unit": "seconds"},
    "deep_sleep_duration": {"label": "深睡时长", "unit": "seconds"},
    "rem_sleep_duration": {"label": "REM睡眠时长", "unit": "seconds"},
    "awake_time": {"label": "清醒时长", "unit": "seconds"},
    "efficiency": {"label": "睡眠效率", "unit": "percent"},
    "average_heart_rate": {"label": "平均心率", "unit": "bpm"},
    "lowest_heart_rate": {"label": "最低心率", "unit": "bpm"},
    "average_hrv": {"label": "平均HRV", "unit": "ms"},
    "average_breath": {"label": "平均呼吸率", "unit": "breaths_per_minute"},
}

TIME_DURATION_METADATA = {
    "bedtime_start": {"label": "入睡/睡眠开始时间", "unit": "datetime"},
    "bedtime_end": {"label": "醒来/睡眠结束时间", "unit": "datetime"},
    "total_sleep_duration": {"label": "总睡眠时长", "unit": "seconds"},
    "time_in_bed": {"label": "卧床时长", "unit": "seconds"},
    "deep_sleep_duration": {"label": "深睡时长", "unit": "seconds"},
    "rem_sleep_duration": {"label": "REM睡眠时长", "unit": "seconds"},
    "awake_time": {"label": "睡后清醒时长", "unit": "seconds"},
    "latency": {"label": "入睡潜伏期", "unit": "seconds"},
}

P02_CONTEXT_METADATA = {
    **TIME_DURATION_METADATA,
    "efficiency": {"label": "睡眠效率", "unit": "percent"},
}


def _load_long_sleep():
    df = pd.read_csv(resolve_sleep_data_path())
    df["day_dt"] = pd.to_datetime(df["day"], errors="coerce")
    return (
        df[df["type"].astype(str).str.lower().eq("long_sleep")]
        .dropna(subset=["day_dt"])
        .sort_values("day_dt")
        .copy()
    )

def get_night_and_baseline(query_context_date: str, baseline_n: int = 7):
    long_sleep = _load_long_sleep()
    target = pd.to_datetime(query_context_date)
    rows = long_sleep[long_sleep["day_dt"] == target]
    if rows.empty:
        return {"available": False, "reason": "没有找到对应主睡眠数据"}

    row = rows.iloc[-1]
    prev = long_sleep[long_sleep["day_dt"] < target].tail(baseline_n)
    fields = [
        "total_sleep_duration","deep_sleep_duration","rem_sleep_duration","awake_time",
        "efficiency","average_heart_rate","lowest_heart_rate","average_hrv","average_breath"
    ]
    night, baseline = {}, {}
    for f in fields:
        if f not in long_sleep.columns:
            continue
        v = pd.to_numeric(pd.Series([row.get(f)]), errors="coerce").iloc[0]
        night[f] = None if pd.isna(v) else float(v)
        vals = pd.to_numeric(prev[f], errors="coerce").dropna()
        baseline[f] = None if vals.empty else float(vals.mean())

    return {
        "available": True,
        "query_context_date": query_context_date,
        "source_session_id": str(row.get("id")),
        "bedtime_start": str(row.get("bedtime_start")),
        "bedtime_end": str(row.get("bedtime_end")),
        "night": night,
        "baseline_7d": baseline,
    }


def get_time_duration_metric(query_context_date: str, metric: str):
    metadata = TIME_DURATION_METADATA.get(metric)
    if not metadata:
        return {"available": False, "reason": f"P02暂不支持字段：{metric}"}
    long_sleep = _load_long_sleep()
    target = pd.to_datetime(query_context_date)
    rows = long_sleep[long_sleep["day_dt"] == target]
    if rows.empty:
        return {"available": False, "reason": "没有找到对应主睡眠数据"}
    row = rows.iloc[-1]
    value = row.get(metric)
    if pd.isna(value):
        return {"available": False, "reason": f"没有找到{metadata['label']}数据"}
    if metadata["unit"] == "seconds":
        value = float(value)
    else:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return {"available": False, "reason": f"{metadata['label']}格式不可用"}
        value = parsed.isoformat()
    return {
        "available": True,
        "query_context_date": query_context_date,
        "source_session_id": str(row.get("id")),
        "metric": metric,
        "metric_label": metadata["label"],
        "unit": metadata["unit"],
        "value": value,
        "timezone": "source_data_timezone_not_provided",
        "coverage_note": "当前Demo仅使用目标日期对应的主睡眠记录。",
    }


def _clock_minutes(value):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return int(parsed.hour) * 60 + int(parsed.minute)


def _shortest_clock_delta(current_minutes, baseline_minutes):
    return ((float(current_minutes) - float(baseline_minutes) + 720) % 1440) - 720


def _clock_baseline(values, metric):
    minutes = [item for item in (_clock_minutes(value) for value in values) if item is not None]
    if not minutes:
        return None
    # 夜间入睡时间可能跨过午夜。将凌晨时间临时移到24点以后再求中心值，
    # 避免23:50和00:10被错误平均到中午。
    unwrapped = [value + 1440 if metric == "bedtime_start" and value < 720 else value for value in minutes]
    center_unwrapped = float(pd.Series(unwrapped).mean())
    center = center_unwrapped % 1440
    deviations = [abs(_shortest_clock_delta(value, center)) for value in minutes]
    mad = float(pd.Series(deviations).median()) if deviations else 0.0
    return {
        "center": center,
        "unit": "clock_minutes",
        "valid_sessions": len(minutes),
        "mad": mad,
    }


def _numeric_baseline(values, unit):
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if numeric.empty:
        return None
    center = float(numeric.mean())
    median = float(numeric.median())
    mad = float((numeric - median).abs().median())
    return {
        "center": center,
        "unit": unit,
        "valid_sessions": int(len(numeric)),
        "mad": mad,
    }


def get_p02_context(query_context_date: str, metric: str, baseline_n: int = 7):
    """Return P02's requested fact, companion facts and personal-history inputs.

    This function intentionally returns structured data rather than user-facing prose.
    The final wording remains the responsibility of the answer-generation model.
    """
    metadata = TIME_DURATION_METADATA.get(metric)
    if not metadata:
        return {"available": False, "reason": f"P02暂不支持字段：{metric}"}

    long_sleep = _load_long_sleep()
    target = pd.to_datetime(query_context_date)
    rows = long_sleep[long_sleep["day_dt"] == target]
    if rows.empty:
        return {"available": False, "reason": "没有找到对应主睡眠数据"}

    row = rows.iloc[-1]
    previous = long_sleep[long_sleep["day_dt"] < target].tail(baseline_n)
    current = {}
    baseline = {}

    for field, field_meta in P02_CONTEXT_METADATA.items():
        if field not in long_sleep.columns:
            continue
        raw_value = row.get(field)
        if field_meta["unit"] == "datetime":
            parsed = pd.to_datetime(raw_value, errors="coerce")
            current[field] = None if pd.isna(parsed) else parsed.isoformat()
            baseline_value = _clock_baseline(previous[field].tolist(), field)
        else:
            numeric = pd.to_numeric(pd.Series([raw_value]), errors="coerce").iloc[0]
            current[field] = None if pd.isna(numeric) else float(numeric)
            baseline_value = _numeric_baseline(previous[field].tolist(), field_meta["unit"])
        if baseline_value:
            baseline[field] = baseline_value

    requested_value = current.get(metric)
    if requested_value is None:
        return {"available": False, "reason": f"没有找到{metadata['label']}数据"}

    source_value = str(row.get(metric))
    timezone_status = (
        "source_offset_present"
        if metadata["unit"] == "datetime" and ("+" in source_value[10:] or source_value.endswith("Z"))
        else "source_timezone_not_confirmed"
    )
    return {
        "available": True,
        "query_context_date": query_context_date,
        "source_session_id": str(row.get("id")),
        "metric": metric,
        "metric_label": metadata["label"],
        "unit": metadata["unit"],
        "value": requested_value,
        "current": current,
        "baseline": {
            "window": f"此前最近{baseline_n}个有效主睡眠",
            "requested_sessions": baseline_n,
            "metrics": baseline,
        },
        "internal_metadata": {
            "timezone_status": timezone_status,
            "coverage_note": "当前Demo采用query_context_date当天醒来的long_sleep作为昨晚主睡眠。",
        },
    }


def get_period_comparison(query_context_date: str, metric: str, window_n: int = 7):
    if metric not in METRIC_METADATA:
        return {"available": False, "reason": f"P11暂不支持指标：{metric}"}
    long_sleep = _load_long_sleep()
    target = pd.to_datetime(query_context_date)
    eligible = long_sleep[long_sleep["day_dt"] <= target].copy()
    if metric not in eligible.columns:
        return {"available": False, "reason": f"数据中没有字段：{metric}"}
    eligible[metric] = pd.to_numeric(eligible[metric], errors="coerce")
    eligible = eligible.dropna(subset=[metric])
    current = eligible.tail(window_n)
    previous = eligible.iloc[:-len(current)].tail(window_n) if len(current) else eligible.iloc[0:0]
    if len(current) < 2 or len(previous) < 2:
        return {
            "available": False,
            "reason": "可比历史记录不足，至少需要当前和上一时间窗各2条有效记录",
            "current_valid_sessions": len(current),
            "previous_valid_sessions": len(previous),
        }
    current_mean = float(current[metric].mean())
    previous_mean = float(previous[metric].mean())
    delta = current_mean - previous_mean
    return {
        "available": True,
        "query_context_date": query_context_date,
        "metric": metric,
        "metric_label": METRIC_METADATA[metric]["label"],
        "unit": METRIC_METADATA[metric]["unit"],
        "current_window": {
            "label": f"最近{len(current)}次有效主睡眠",
            "valid_sessions": len(current),
            "start_date": current["day_dt"].min().date().isoformat(),
            "end_date": current["day_dt"].max().date().isoformat(),
            "mean": current_mean,
        },
        "previous_window": {
            "label": f"此前{len(previous)}次有效主睡眠",
            "valid_sessions": len(previous),
            "start_date": previous["day_dt"].min().date().isoformat(),
            "end_date": previous["day_dt"].max().date().isoformat(),
            "mean": previous_mean,
        },
        "delta": delta,
        "direction": "higher" if delta > 0 else "lower" if delta < 0 else "stable",
        "comparison_limit": "这里只描述两个同口径时间窗的变化，不推断变化原因。",
    }


def get_single_metric(query_context_date: str, metric: str, full=None):
    if metric not in METRIC_METADATA:
        return {
            "available": False,
            "reason": f"暂不支持指标：{metric}",
        }

    full = full or get_night_and_baseline(query_context_date)
    if not full.get("available"):
        return full

    value = full["night"].get(metric)
    if value is None:
        return {
            "available": False,
            "reason": f"没有找到{METRIC_METADATA[metric]['label']}数据",
        }

    return {
        "available": True,
        "query_context_date": query_context_date,
        "source_session_id": full["source_session_id"],
        "bedtime_start": full["bedtime_start"],
        "bedtime_end": full["bedtime_end"],
        "metric": metric,
        "metric_label": METRIC_METADATA[metric]["label"],
        "unit": METRIC_METADATA[metric]["unit"],
        "night": {metric: value},
    }
