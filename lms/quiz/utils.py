import os
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas 
from pypdf import PdfReader,PdfWriter 
from user.models import TraineeProfile,EmployeeProfile
import openai 
from dotenv import load_dotenv 
import json
import requests
import re

def generate_certificate(user, quiz, score, passed, date_attempted):
    # Select the template based on whether the user passed or failed the quiz
    template_filename = 'certificate_e.pdf' if passed else 'certificate_c.pdf'
    
    # Create a temporary PDF with user details to overlay on the template
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica", 22)
    
    employee=TraineeProfile.objects.get(user=user)
    employee_name=employee.name
    department = employee.department
    
    # Draw text onto the temporary PDF
    c.drawString(400, 410, f"{employee_name}")
    c.drawString(390, 342, f"{department}")
    c.drawString(400, 290, f"{quiz.topic}")  # Assuming quiz_name is the correct field
    c.drawString(420, 236, f"{score:.2f}%")
    c.drawString(405, 157, f"{date_attempted.strftime('%d-%m-%Y')}")

    # c.setFont("Helvetica", 16)
    # c.drawString(395, 390, f"from {school_name}")

    
    c.save()
    buffer.seek(0)

    # Load the template PDF
    template_path = os.path.join(settings.MEDIA_ROOT, template_filename)
    template_reader = PdfReader(template_path)
    template_writer = PdfWriter()
    
    # Overlay the content on the template PDF
    template_page = template_reader.pages[0]
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