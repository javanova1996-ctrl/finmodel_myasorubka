from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.excel_loader import READABLE_METRICS, load_workbook_data
from src.model import Scenario, aggregate_total, build_forecast, yearly_summary

st.set_page_config(page_title="Финмодель Мясорубка", layout="wide")

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "ОПиУ_2026_АНАЛИТИКА.xlsx"


@st.cache_data
def get_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    wb_data = load_workbook_data(DATA_PATH)
    return wb_data.history, wb_data.baseline


history, baseline = get_data()
entities = [e for e in baseline["entity"].tolist() if e != "ИТОГО"]

st.title("Интерактивная финмодель — Мясорубка")
st.caption("Источник данных: Excel-модель ОПиУ 2026. В приложении факт за январь–март и сценарный прогноз на апрель–декабрь.")

with st.sidebar:
    st.header("Сценарий")
    scenario_name = st.selectbox("Готовый сценарий", ["Base", "Optimistic", "Downside", "Custom"])

    presets = {
        "Base": (2.0, 0.0, 1.0),
        "Optimistic": (5.0, -2.0, 0.5),
        "Downside": (-2.0, 2.0, 1.5),
        "Custom": (2.0, 0.0, 1.0),
    }
    default_growth, default_var_delta, default_fixed_growth = presets[scenario_name]

    global_revenue_growth_pct = st.slider("Рост выручки в месяц, %", -20.0, 20.0, float(default_growth), 0.5)
    global_var_cost_delta_pp = st.slider("Изменение доли переменных затрат, п.п.", -15.0, 15.0, float(default_var_delta), 0.5)
    global_fixed_cost_growth_pct = st.slider("Рост постоянных затрат в месяц, %", -10.0, 15.0, float(default_fixed_growth), 0.5)

    st.markdown("### Корректировки по подразделениям")
    growth_adjustments = {}
    var_adjustments = {}
    fixed_adjustments = {}
    for entity in entities:
        with st.expander(entity, expanded=False):
            growth_adjustments[entity] = st.number_input(
                f"{entity}: доп. рост выручки, %", value=0.0, step=0.5, key=f"g_{entity}"
            )
            var_adjustments[entity] = st.number_input(
                f"{entity}: сдвиг переменных затрат, п.п.", value=0.0, step=0.5, key=f"v_{entity}"
            )
            fixed_adjustments[entity] = st.number_input(
                f"{entity}: рост постоянных затрат, %", value=0.0, step=0.5, key=f"f_{entity}"
            )

scenario = Scenario(
    global_revenue_growth_pct=global_revenue_growth_pct,
    global_var_cost_delta_pp=global_var_cost_delta_pp,
    global_fixed_cost_growth_pct=global_fixed_cost_growth_pct,
    entity_growth_pct=growth_adjustments,
    entity_var_delta_pp=var_adjustments,
    entity_fixed_growth_pct=fixed_adjustments,
)

combined = build_forecast(history=history, baseline=baseline, scenario=scenario)
total_df = aggregate_total(combined[combined["entity"] != "ИТОГО"])
combined = pd.concat([combined, total_df], ignore_index=True)

st.subheader("Ключевые показатели")
full_year_total = yearly_summary(combined[combined["entity"] == "ИТОГО"])
fy = full_year_total.iloc[0]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Выручка 2026", f"{fy['revenue']:,.0f} ₽".replace(",", " "))
col2.metric("Валовая прибыль 2026", f"{fy['gross_profit']:,.0f} ₽".replace(",", " "))
col3.metric("Чистая прибыль 2026", f"{fy['net_profit']:,.0f} ₽".replace(",", " "))
col4.metric("Чистая маржа 2026", f"{fy['net_margin']:.1%}")

chart_base = combined[combined["entity"] == "ИТОГО"].sort_values("month_order")

st.subheader("Динамика ИТОГО")
metric_choice = st.selectbox(
    "Показатель для графика",
    ["revenue", "gross_profit", "net_profit", "variable_costs", "fixed_costs"],
    format_func=lambda x: READABLE_METRICS.get(x, x),
)
st.line_chart(chart_base.set_index("month")[metric_choice])

left, right = st.columns([1.2, 1])
with left:
    st.subheader("Факт + прогноз по месяцам")
    display = chart_base[["month", "type", "revenue", "variable_costs", "fixed_costs", "gross_profit", "net_profit", "gross_margin", "net_margin"]].copy()
    for col in ["revenue", "variable_costs", "fixed_costs", "gross_profit", "net_profit"]:
        display[col] = display[col].round(0)
    for col in ["gross_margin", "net_margin"]:
        display[col] = display[col].map(lambda x: f"{x:.1%}")
    st.dataframe(display, use_container_width=True, hide_index=True)

with right:
    st.subheader("Итоги по подразделениям")
    summary = yearly_summary(combined[combined["entity"] != "ИТОГО"]).copy()
    summary["gross_margin"] = summary["gross_margin"].map(lambda x: f"{x:.1%}")
    summary["net_margin"] = summary["net_margin"].map(lambda x: f"{x:.1%}")
    for col in ["revenue", "variable_costs", "fixed_costs", "gross_profit", "net_profit"]:
        summary[col] = summary[col].round(0)
    st.dataframe(summary, use_container_width=True, hide_index=True)

st.subheader("Помесячная детализация по подразделению")
selected_entity = st.selectbox("Подразделение", ["ИТОГО"] + entities)
entity_df = combined[combined["entity"] == selected_entity].sort_values("month_order")
entity_display = entity_df[["month", "type", "revenue", "variable_costs", "fixed_costs", "gross_profit", "net_profit", "gross_margin", "net_margin"]].copy()
for col in ["revenue", "variable_costs", "fixed_costs", "gross_profit", "net_profit"]:
    entity_display[col] = entity_display[col].round(0)
for col in ["gross_margin", "net_margin"]:
    entity_display[col] = entity_display[col].map(lambda x: f"{x:.1%}")
st.dataframe(entity_display, use_container_width=True, hide_index=True)

st.subheader("Историческая база из Excel")
history_view = history[["entity", "month", "revenue", "variable_costs", "fixed_costs", "gross_profit", "net_profit", "gross_margin", "net_margin"]].copy()
for col in ["revenue", "variable_costs", "fixed_costs", "gross_profit", "net_profit"]:
    history_view[col] = history_view[col].round(0)
for col in ["gross_margin", "net_margin"]:
    history_view[col] = history_view[col].map(lambda x: f"{x:.1%}")
st.dataframe(history_view, use_container_width=True, hide_index=True)

csv = combined.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Скачать результат сценария в CSV",
    data=csv,
    file_name="finmodel_scenario_export.csv",
    mime="text/csv",
)
