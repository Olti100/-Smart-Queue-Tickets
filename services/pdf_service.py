from io import BytesIO

from reportlab.lib.pagesizes import A6
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from services.qr_service import generate_qr_bytes


def generate_ticket_pdf(ticket, org_name: str, department_name: str, service_name: str, estimated_wait: int) -> bytes:
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=A6)
    c.setTitle(f"Ticket {ticket.ticket_number}")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(20, 390, org_name)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(20, 360, f"Ticket: {ticket.ticket_number}")

    c.setFont("Helvetica", 10)
    c.drawString(20, 336, f"Department: {department_name}")
    c.drawString(20, 320, f"Service: {service_name}")
    c.drawString(20, 304, f"Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    c.drawString(20, 288, f"Estimated Wait: {estimated_wait} minutes")
    c.drawString(20, 272, f"Priority: {ticket.priority_category.value}")

    qr_payload = f"{ticket.ticket_number}|{department_name}|{service_name}|{ticket.created_at.isoformat()}"
    qr_data = generate_qr_bytes(qr_payload)
    qr_image = ImageReader(BytesIO(qr_data))
    c.drawImage(qr_image, 145, 245, width=100, height=100)

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(20, 240, "Please be ready when your ticket is called.")
    c.showPage()
    c.save()
    packet.seek(0)
    return packet.read()
