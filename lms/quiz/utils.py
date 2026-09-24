import os
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
from reportlab.pdfgen import canvas 
from pypdf import PdfReader,PdfWriter 
from user.models import TraineeProfile,EmployeeProfile
import openai 
from dotenv import load_dotenv 
import json
import requests
import re

# Blank lines on the certificate templates, in PDF points: (x_start, x_end, baseline_y)
CERTIFICATE_SLOTS = {
    'name': (335, 665, 410),
    'department': (335, 440, 344),
    'topic': (335, 665, 286),
    'score': (370, 530, 236),
    'date': (405, 540, 154),
}


def draw_in_slot(c, text, slot, font="Helvetica", max_size=22, min_size=9):
    """Draw text centred on a template line, shrinking (then truncating) it to fit."""
    x_start, x_end, y = slot
    max_width = x_end - x_start - 6
    size = max_size
    while size > min_size and c.stringWidth(text, font, size) > max_width:
        size -= 0.5
    while len(text) > 1 and c.stringWidth(text, font, size) > max_width:
        text = text[:-2] + "…"
    c.setFont(font, size)
    c.drawCentredString((x_start + x_end) / 2, y, text)


def generate_certificate(user, quiz, score, passed, date_attempted):
    # Select the template based on whether the user passed or failed the quiz
    template_filename = 'certificate_e.pdf' if passed else 'certificate_c.pdf'

    # Load the template PDF
    template_path = os.path.join(settings.MEDIA_ROOT, template_filename)
    template_reader = PdfReader(template_path)
    template_writer = PdfWriter()
    template_page = template_reader.pages[0]

    # Create a temporary PDF with user details to overlay on the template,
    # the same size as the template so nothing gets clipped
    buffer = BytesIO()
    page_size = (float(template_page.mediabox.width), float(template_page.mediabox.height))
    c = canvas.Canvas(buffer, pagesize=page_size)

    profile = (TraineeProfile.objects.filter(user=user).first()
               or EmployeeProfile.objects.filter(user=user).first())
    employee_name = (profile.name if profile else "") or user.get_full_name() or user.username
    department = profile.department if profile else quiz.department

    # Draw text onto the temporary PDF
    draw_in_slot(c, f"{employee_name}", CERTIFICATE_SLOTS['name'])
    draw_in_slot(c, f"{department}", CERTIFICATE_SLOTS['department'])
    draw_in_slot(c, f"{quiz.topic}", CERTIFICATE_SLOTS['topic'])
    draw_in_slot(c, f"{score:.2f}%", CERTIFICATE_SLOTS['score'])
    draw_in_slot(c, f"{date_attempted.strftime('%d-%m-%Y')}", CERTIFICATE_SLOTS['date'])

    c.save()
    buffer.seek(0)

    # Overlay the content on the template PDF
    overlay_pdf = PdfReader(buffer)
    overlay_page = overlay_pdf.pages[0]
    
    template_page.merge_page(overlay_page)
    template_writer.add_page(template_page)

    # Save the final PDF to a buffer
    final_buffer = BytesIO()
    template_writer.write(final_buffer)
    final_buffer.seek(0)
    
    # Create a ContentFile for saving
    filename = f"{user.username}_{quiz.quiz_name}_certificate.pdf"
    return ContentFile(final_buffer.getvalue(), filename)