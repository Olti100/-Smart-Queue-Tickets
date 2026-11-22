import streamlit as st


def kpi_card(title: str, value: str, color: str = "#2563EB"):
    st.markdown(
        f"""
        <div class='kpi-card' style='border-left: 6px solid {color};'>
            <div class='kpi-title'>{title}</div>
            <div class='kpi-value'>{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
