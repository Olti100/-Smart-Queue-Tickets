from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from core.analytics_engine import AnalyticsEngine
from modules.authentication import require_roles


def _build_pdf_report(kpis: dict, title: str) -> bytes:
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 800, title)
    c.setFont("Helvetica", 11)
    y = 770
    for key, value in kpis.items():
        c.drawString(40, y, f"{key}: {value}")
        y -= 18
    c.save()
    packet.seek(0)
    return packet.read()


def render(session, user: dict):
    if not require_roles(["ADMIN", "MANAGER"]):
        return

    st.title("Reports & Exports")

    period = st.selectbox("Period", ["Daily", "Weekly", "Monthly"])
    end = datetime.utcnow()
    days = {"Daily": 1, "Weekly": 7, "Monthly": 30}[period]
    start = end - timedelta(days=days)

    analytics = AnalyticsEngine(session)
    kpis = analytics.kpis(start, end)
    st.json(kpis)

    df = analytics.tickets_dataframe(start, end)

    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button("Export CSV", csv_data, file_name=f"queue_{period.lower()}.csv", mime="text/csv")

    excel_io = BytesIO()
    with pd.ExcelWriter(excel_io, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="tickets")
    st.download_button(
        "Export Excel",
        excel_io.getvalue(),
        file_name=f"queue_{period.lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    pdf_data = _build_pdf_report(kpis, f"Smart Queue {period} Report")
    st.download_button("Export PDF", pdf_data, file_name=f"queue_{period.lower()}.pdf", mime="application/pdf")
