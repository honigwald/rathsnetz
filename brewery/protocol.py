import io
from django.http import FileResponse
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.platypus.tables import Table, TableStyle
from reportlab.lib import colors
from .models import Charge, RecipeProtocol, FermentationProtocol
from .ispindel import get_plot
import os
from pathlib import Path

AMOUNT_FACTOR = 100
BASE_DIR = Path(__file__).resolve().parent.parent

class RotatedImage(Image):

    def wrap(self,availWidth,availHeight):
        h, w = Image.wrap(self,availHeight,availWidth)
        return w, h
    def draw(self):
        self.canv.rotate(90)
        Image.draw(self)

def processing_pdf(cid):
    c = Charge.objects.get(pk=cid)

    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=72,leftMargin=72,
                            topMargin=72,bottomMargin=18,
                            title=str(c)+"_protokoll")

    content = []
    sample_style_sheet = getSampleStyleSheet()
    # if you want to see all the sample styles, this prints them
    sample_style_sheet.list()

    logo = Image(os.path.join(BASE_DIR, 'static/img/logo-white-long.png'), width=384, height=80)
    title = Paragraph("Protokoll: "+c.recipe.name, sample_style_sheet['Heading1'])
    p1title = Paragraph("Parameter", sample_style_sheet['Heading2'])

    p1text = []
    p1text.append(Paragraph("<u>Braumeister</u>: " + str(c.brewmaster), sample_style_sheet['BodyText']))
    p1text.append(Paragraph("<u>Charge</u>: " + str(c), sample_style_sheet['BodyText']))
    p1text.append(Paragraph("<u>Brautag</u>: " + str(c.production), sample_style_sheet['BodyText']))
    p1text.append(Paragraph("<u>Gesamtdauer</u>: " + str(c.duration), sample_style_sheet['BodyText']))
    p1text.append(Paragraph("<u>Menge</u>: " + str(c.amount), sample_style_sheet['BodyText']))
    hg =  c.amount * c.recipe.hg / AMOUNT_FACTOR
    ng =  c.amount * c.recipe.ng / AMOUNT_FACTOR
    p1text.append(Paragraph("<u>Wasser</u>: " + str(hg) + " Liter / " + str(ng) + " Liter", sample_style_sheet['BodyText']))
    p1text.append(Paragraph("<u>Ausstoß</u>: " + str(c.output), sample_style_sheet['BodyText']))
    p1text.append(Paragraph("<u>Restextrakt</u>: " + str(c.restextract), sample_style_sheet['BodyText']))
    p1text.append(Paragraph("<u>Stammwürze</u>: " + str(c.reached_wort), sample_style_sheet['BodyText']))
    # calculate evg and alc
    try:
        real_restextract = 0.1808 * c.reached_wort + 0.8192 - c.restextract
        evg = (c.reached_wort - real_restextract) * 100 / c.reached_wort
        alc = (c.reached_wort - real_restextract) / (2.0665 - 0.010665 * c.reached_wort)
    except:
        evg = None
        alc = None
    p1text.append(Paragraph("<u>EVG</u>: " + str(evg), sample_style_sheet['BodyText']))
    p1text.append(Paragraph("<u>Alkohol</u>: " + str(alc), sample_style_sheet['BodyText']))

    # Page 1
    content.append(logo)
    content.append(Spacer(1, 12))
    content.append(title)
    content.append(p1title)
    content.append(Spacer(1, 12))
    for item in p1text:
        content.append(item)
    content.append(PageBreak())

    # Page 2
    GRID_STYLE = TableStyle(
            [('GRID', (0,0), (-1,-1), 0.25, colors.black),
             ('ALIGN', (1,1), (-1,-1), 'LEFT')]
            )

    p2title = Paragraph("Brauprotokoll", sample_style_sheet['Heading2'])
    content.append(p2title)
    data = []
    theader = ("Nr", "Titel", "Zutaten", "Dauer")
    data.append(theader)
    protocol = RecipeProtocol.objects.filter(charge=c.id)
    for step in protocol:
        row = []
        row.append(step.step)
        row.append(step.title)
        row.append(step.ingredient)
        row.append(step.duration)
        data.append(row)

    table = Table(data, colWidths=[20,120,250,50])
    table.setStyle(GRID_STYLE)
    content.append(table)

    content.append(PageBreak())

    # Page 3
    p3title = Paragraph("Gärverlauf", sample_style_sheet['Heading2'])
    content.append(p3title)
    if c.ispindel:
        get_plot(c)
        content.append(Image('/tmp/ispindelfig.png'))
    else:
        data = []
        fprotocol = FermentationProtocol.objects.filter(charge=c.id)
        theader = ("Nr", "Zeitpunkt", "Temperatur", "Plato")
        data.append(theader)
        for step in fprotocol:
            row = []
            row.append(step.step)
            row.append(step.date)
            row.append(step.temperature)
            row.append(step.plato)
            data.append(row)
        table = Table(data, colWidths=[20,160,250,50])
        table.setStyle(GRID_STYLE)
        content.append(table)

    pdf.build(content)
    buffer.seek(0)
    return buffer
