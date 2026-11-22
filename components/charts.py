import plotly.express as px
import streamlit as st


def render_bar(df, x: str, y: str, title: str, color: str = "#2563EB"):
    if df.empty:
        st.info("No data available for this chart.")
        return
    fig = px.bar(df, x=x, y=y, title=title)
    fig.update_traces(marker_color=color)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


def render_line(df, x: str, y: str, title: str):
    if df.empty:
        st.info("No data available for this chart.")
        return
    fig = px.line(df, x=x, y=y, title=title, markers=True)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
