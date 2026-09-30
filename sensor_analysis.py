"""Sensor CSV stats, IQR/z-score outliers, and Plotly charts. No LLM."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import DEMO_DIR, SENSORS_DIR, ensure_folders

CSV_CANDIDATES = [
    SENSORS_DIR / "sensor_data.csv",
    DEMO_DIR / "sensor_data.csv",
]

CHART_COLORS = ["#E8A84A", "#FF6B4A", "#3DD68C", "#7AA2FF", "#C4B5FD", "#F472B6"]


def sensor_csv_path() -> Path | None:
    ensure_folders()
    for path in CSV_CANDIDATES:
        if path.exists():
            return path
    return None


def load_sensor_frame(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or sensor_csv_path()
    if csv_path is None:
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if col != "timestamp" and pd.api.types.is_numeric_dtype(df[col])]


def summarize_sensors(df: pd.DataFrame) -> dict:
    """Row count, missing values, mean, min, max, and std. Calculated with NumPy."""
    columns = numeric_columns(df)
    stats = []
    for col in columns:
        values = df[col].to_numpy(dtype=float)
        missing = int(np.isnan(values).sum())
        clean = values[~np.isnan(values)]
        if clean.size == 0:
            mean = minimum = maximum = std = None
        else:
            mean = float(np.mean(clean))
            minimum = float(np.min(clean))
            maximum = float(np.max(clean))
            std = float(np.std(clean, ddof=1)) if clean.size > 1 else 0.0
        stats.append(
            {
                "column": col,
                "missing_values": missing,
                "mean": mean,
                "minimum": minimum,
                "maximum": maximum,
                "standard_deviation": std,
            }
        )
    return {
        "row_count": int(len(df)),
        "missing_values": int(df.isna().to_numpy().sum()),
        "stats": pd.DataFrame(stats),
    }


def detect_anomalies(df: pd.DataFrame, method: str = "iqr", z_threshold: float = 2.5) -> pd.DataFrame:
    """Flag outliers with IQR (1.5x) or z-score. No LLM."""
    method = "zscore" if method.lower() in {"z-score", "zscore", "z"} else "iqr"
    rows = []
    for col in numeric_columns(df):
        values = df[col].to_numpy(dtype=float)
        valid = ~np.isnan(values)
        clean = values[valid]
        if clean.size < 4:
            continue
        if method == "zscore":
            mu = float(np.mean(clean))
            sigma = float(np.std(clean, ddof=1))
            if sigma == 0:
                continue
            z = np.abs((values - mu) / sigma)
            mask = valid & (z > z_threshold)
            detail = f"|z| > {z_threshold:g}"
        else:
            q1 = float(np.percentile(clean, 25))
            q3 = float(np.percentile(clean, 75))
            iqr = q3 - q1
            low = q1 - 1.5 * iqr
            high = q3 + 1.5 * iqr
            mask = valid & ((values < low) | (values > high))
            detail = f"outside [{low:.3g}, {high:.3g}]"

        for index in np.where(mask)[0]:
            item = {
                "row": int(index),
                "column": col,
                "value": float(values[index]),
                "method": "IQR" if method == "iqr" else "z-score",
                "detail": detail,
            }
            if "timestamp" in df.columns:
                item["timestamp"] = df.iloc[int(index)]["timestamp"]
            rows.append(item)
    return pd.DataFrame(rows)


def flag_rows(df: pd.DataFrame) -> pd.DataFrame:
    anomalies = detect_anomalies(df, method="iqr")
    if anomalies.empty:
        return pd.DataFrame(columns=["timestamp", "reasons"])
    grouped = []
    for _, part in anomalies.groupby("row"):
        reasons = "; ".join(f"{item.column}={item.value:g}" for item in part.itertuples())
        grouped.append(
            {
                "timestamp": part.iloc[0]["timestamp"] if "timestamp" in part.columns else None,
                "reasons": reasons,
            }
        )
    return pd.DataFrame(grouped)


def latest_status(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"label": "No data", "tone": "muted", "detail": "Upload sensor_data.csv"}
    flags = flag_rows(df)
    if flags.empty:
        return {"label": "Normal", "tone": "ok", "detail": "No IQR outliers"}
    return {
        "label": "Attention",
        "tone": "attn",
        "detail": f"{len(flags)} row(s) with IQR outliers",
    }


def _x_axis(df: pd.DataFrame):
    if "timestamp" in df.columns:
        return df["timestamp"]
    return df.index


def build_sensor_figure(df: pd.DataFrame, anomalies: pd.DataFrame | None = None) -> go.Figure:
    columns = numeric_columns(df)
    rows = max(len(columns), 1)
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.04, subplot_titles=columns or ["No numeric columns"])
    if df.empty or not columns:
        fig.update_layout(template="plotly_dark", height=420)
        return fig

    x = _x_axis(df)
    for i, col in enumerate(columns):
        color = CHART_COLORS[i % len(CHART_COLORS)]
        fig.add_trace(
            go.Scatter(x=x, y=df[col], name=col, mode="lines+markers", line=dict(color=color), marker=dict(size=5)),
            row=i + 1,
            col=1,
        )
        if anomalies is not None and not anomalies.empty:
            points = anomalies[anomalies["column"] == col]
            if points.empty:
                continue
            px = points["timestamp"] if "timestamp" in points.columns else points["row"]
            fig.add_trace(
                go.Scatter(
                    x=px,
                    y=points["value"],
                    name=f"{col} outlier",
                    mode="markers",
                    marker=dict(color="#FF6B4A", size=11, symbol="x"),
                ),
                row=i + 1,
                col=1,
            )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#141A22",
        plot_bgcolor="#141A22",
        height=max(520, 140 * rows),
        legend=dict(orientation="h", y=1.04),
        margin=dict(l=40, r=20, t=50, b=40),
        font=dict(color="#D7DEE8"),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor="#243044", zeroline=False)
    fig.update_yaxes(gridcolor="#243044", zeroline=False)
    return fig


def build_box_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(numeric_columns(df)):
        fig.add_trace(
            go.Box(
                y=df[col],
                name=col,
                marker_color=CHART_COLORS[i % len(CHART_COLORS)],
                boxpoints="outliers",
            )
        )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#141A22",
        plot_bgcolor="#141A22",
        height=380,
        margin=dict(l=40, r=20, t=30, b=40),
        font=dict(color="#D7DEE8"),
        showlegend=False,
        title="IQR view (box plots)",
    )
    fig.update_yaxes(gridcolor="#243044", zeroline=False)
    return fig
