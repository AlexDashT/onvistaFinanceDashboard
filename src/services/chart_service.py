"""Build local chart figures for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose

import pandas as pd
import plotly.graph_objects as go

from src.models import ChartPeriod, ChartSeries, WatchlistItem
from src.providers.base import ChartDataUnavailableError, ProviderError
from src.providers.onvista_history_provider import OnvistaHistoryProvider


class ChartServiceError(RuntimeError):
    """Raised when a chart cannot be prepared for rendering."""


GERMAN_MONTH_LABELS = {
    1: "Jan.",
    2: "Feb.",
    3: "März",
    4: "Apr.",
    5: "Mai",
    6: "Juni",
    7: "Juli",
    8: "Aug.",
    9: "Sept.",
    10: "Okt.",
    11: "Nov.",
    12: "Dez.",
}


def format_price_display(value: float, unit: str | None, decimals: int = 3) -> str:
    """Format one numeric price using German separators."""
    formatted_number = f"{value:,.{decimals}f}"
    german_number = formatted_number.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{german_number} {unit}".strip()


@dataclass(frozen=True)
class ChartViewModel:
    """Bundle chart data and summary values for the UI."""

    series: ChartSeries
    figure: go.Figure
    last_price: float
    absolute_change: float
    percent_change: float


class ChartService:
    """Fetch onvista price series and build Plotly figures."""

    def __init__(self, history_provider: OnvistaHistoryProvider) -> None:
        self.history_provider = history_provider

    def build_chart_view(self, item: WatchlistItem, period: ChartPeriod) -> ChartViewModel:
        """Return everything needed to render one chart card."""
        try:
            series = self.history_provider.fetch_chart_series(item=item, period=period)
        except ChartDataUnavailableError as exc:
            raise ChartServiceError(str(exc)) from exc
        except ProviderError as exc:
            raise ChartServiceError(
                f"The chart for {item.display_name} could not be loaded from onvista right now."
            ) from exc

        frame = self.to_dataframe(series)
        if frame.empty:
            raise ChartServiceError(f"No price data is available for {item.display_name}.")

        last_price = float(frame["price"].iloc[-1])
        first_price = float(frame["price"].iloc[0])
        absolute_change = last_price - first_price
        percent_change = 0.0 if first_price == 0 else (absolute_change / first_price) * 100

        return ChartViewModel(
            series=series,
            figure=self._build_figure(item=item, period=period, frame=frame),
            last_price=last_price,
            absolute_change=absolute_change,
            percent_change=percent_change,
        )

    def to_dataframe(self, series: ChartSeries) -> pd.DataFrame:
        """Convert a chart series into a pandas DataFrame."""
        return pd.DataFrame(
            {
                "timestamp": [point.timestamp for point in series.points],
                "price": [point.price for point in series.points],
            }
        )

    def _build_figure(self, item: WatchlistItem, period: ChartPeriod, frame: pd.DataFrame) -> go.Figure:
        """Create an onvista-inspired Plotly price chart."""
        unit = item.currency or ""
        y_min = float(frame["price"].min())
        y_max = float(frame["price"].max())
        y_padding = self._calculate_y_padding(y_min, y_max)
        y_range = [y_min - y_padding, y_max + y_padding]
        x_tick_values, x_tick_labels = self._build_x_ticks(frame=frame, period=period)
        y_tick_values = self._build_y_ticks(y_range=y_range)
        y_tick_labels = [format_price_display(value, unit) for value in y_tick_values]

        custom_data = list(
            zip(
                frame["timestamp"].map(lambda value: self._format_hover_date(value.to_pydatetime())),
                frame["price"].map(lambda value: format_price_display(float(value), unit)),
                strict=True,
            )
        )
        last_timestamp = frame["timestamp"].iloc[-1]
        last_price = float(frame["price"].iloc[-1])

        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=frame["timestamp"],
                y=frame["price"],
                mode="lines",
                line={"color": "#6d28d9", "width": 3},
                customdata=custom_data,
                hovertemplate=(
                    "%{customdata[0]}<br>"
                    + f"{item.display_name}: <b>%{{customdata[1]}}</b>"
                    + "<extra></extra>"
                ),
                name=item.display_name,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[last_timestamp],
                y=[last_price],
                mode="markers",
                marker={"size": 10, "color": "#6d28d9", "line": {"color": "#ffffff", "width": 2}},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.update_layout(
            margin={"l": 20, "r": 92, "t": 8, "b": 22},
            height=390,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            hovermode="closest",
            hoverlabel={
                "bgcolor": "#ffffff",
                "bordercolor": "rgba(15, 23, 42, 0.20)",
                "font": {"color": "#111827", "size": 13},
            },
            xaxis={
                "showgrid": False,
                "zeroline": False,
                "showline": True,
                "linecolor": "rgba(17, 24, 39, 0.65)",
                "linewidth": 1.5,
                "tickfont": {"color": "#111827", "size": 11},
                "title": None,
                "tickvals": x_tick_values,
                "ticktext": x_tick_labels,
                "showspikes": True,
                "spikemode": "across",
                "spikecolor": "rgba(17, 24, 39, 0.35)",
                "spikethickness": 1,
            },
            yaxis={
                "showgrid": True,
                "gridcolor": "rgba(148, 163, 184, 0.28)",
                "zeroline": False,
                "tickfont": {"color": "#111827", "size": 12},
                "title": None,
                "tickmode": "array",
                "tickvals": y_tick_values,
                "ticktext": y_tick_labels,
                "range": y_range,
                "side": "right",
            },
        )
        figure.add_annotation(
            x=1.015,
            xref="paper",
            y=last_price,
            yref="y",
            text=format_price_display(last_price, unit),
            showarrow=False,
            font={"color": "#ffffff", "size": 12},
            bgcolor="#6d28d9",
            bordercolor="#6d28d9",
            borderwidth=1,
            borderpad=4,
        )
        return figure

    def _build_x_ticks(self, frame: pd.DataFrame, period: ChartPeriod) -> tuple[list[pd.Timestamp], list[str]]:
        """Return x-axis tick positions and labels."""
        timestamps = frame["timestamp"]
        start = timestamps.iloc[0]
        end = timestamps.iloc[-1]

        if period is ChartPeriod.DAY_1:
            tick_values = list(pd.date_range(start=start.floor("h"), end=end.ceil("h"), periods=5))
            tick_labels = [value.strftime("%H:%M") for value in tick_values]
            return tick_values, tick_labels

        if period is ChartPeriod.WEEK_1:
            tick_values = list(pd.date_range(start=start.normalize(), end=end.normalize(), periods=5))
            tick_labels = [value.strftime("%d.%m.") for value in tick_values]
            return tick_values, tick_labels

        if period in {ChartPeriod.MONTH_1, ChartPeriod.MONTH_3}:
            frequency = "MS"
        elif period is ChartPeriod.YEAR_1:
            frequency = "2MS"
        elif period is ChartPeriod.YEAR_3:
            frequency = "4MS"
        else:
            frequency = "6MS"

        tick_values = list(pd.date_range(start=start.normalize(), end=end.normalize(), freq=frequency))
        if not tick_values:
            tick_values = [start, end]
        if tick_values[-1] != end:
            tick_values.append(end)

        tick_labels = [self._format_axis_month_label(value.to_pydatetime()) for value in tick_values]
        return tick_values, tick_labels

    def _build_y_ticks(self, y_range: list[float]) -> list[float]:
        """Return evenly spaced y-axis ticks within the visible price range."""
        tick_count = 6
        step = (y_range[1] - y_range[0]) / (tick_count - 1)
        return [y_range[0] + (step * index) for index in range(tick_count)]

    def _calculate_y_padding(self, y_min: float, y_max: float) -> float:
        """Return a small padding so the chart does not hug the edges."""
        if isclose(y_min, y_max):
            baseline = abs(y_max) if y_max else 1.0
            return baseline * 0.03
        return max((y_max - y_min) * 0.08, abs(y_max) * 0.01)

    def _format_axis_month_label(self, value: pd.Timestamp | object) -> str:
        """Format monthly axis labels similar to the onvista chart."""
        if isinstance(value, pd.Timestamp):
            timestamp = value.to_pydatetime()
        else:
            timestamp = value
        return f"{GERMAN_MONTH_LABELS[timestamp.month]} {timestamp.year}"

    def _format_hover_date(self, timestamp: object) -> str:
        """Format hover dates with a friendly German-style label."""
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()
        return timestamp.strftime("%d.%m.%Y %H:%M")
