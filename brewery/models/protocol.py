import logging

from django.db import models
from datetime import datetime
from base64 import urlsafe_b64encode as b64e, urlsafe_b64decode as b64d
from reportlab.platypus import Image

from brewery.models import FermentationProtocolStep
from brewery.models import BrewProtocolStep
from brewery.utils import load_dynamic_bg_image, AMOUNT_FACTOR


"""
import os
import io
from pathlib import Path
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.platypus.tables import Table, TableStyle
from reportlab.lib import colors

BASE_DIR = Path(__file__).resolve().parent.parent
"""


class BrewProtocol(models.Model):
    id = models.AutoField(primary_key=True)
    pid = models.CharField(max_length=200, blank=True, null=True)
    rname = models.CharField(max_length=25)
    head = models.ForeignKey(
        BrewProtocolStep,
        related_name="protocol_head",
        on_delete=models.CASCADE,
        null=True,
    )
    tail = models.ForeignKey(
        BrewProtocolStep,
        related_name="protocol_tail",
        on_delete=models.CASCADE,
        null=True,
    )

    def list(self):
        return self.head.dict().values()

    def __str__(self):
        return str(self.pid) + "." + str(self.rname)

    def add_step(self, current_step, comment, tstart):
        protocol_step = BrewProtocolStep(
            pos=current_step.pos,
            rname=current_step.rname,
            title=current_step.title,
            description=current_step.description,
            ingredient=current_step.ingredient,
            amount=current_step.amount,
            unit=current_step.unit,
            comment=comment,
            tstart=tstart,
            tend=datetime.now(),
        )
        protocol_step.save()

        if self.head is None:
            self.head = self.tail = protocol_step
        else:
            protocol_step.previous = self.tail
            protocol_step.save()
            self.refresh_from_db()
            protocol_step.previous.next = protocol_step
            protocol_step.previous.save()
            self.tail = protocol_step
        self.save()

    def context(self, charge):
        context = {}
        context["charge"] = charge
        context["protocol"] = self.list()
        context["hg"] = charge.amount * charge.recipe.hg / AMOUNT_FACTOR
        context["ng"] = charge.amount * charge.recipe.ng / AMOUNT_FACTOR
        context["navi"] = "brewing"
        context["image_url"] = load_dynamic_bg_image()
        try:
            # Scheinbarer EVG (%) = (1 - SRE [°P] / Stammwürze [°P]) · 100
            EVG_f = (1 - charge.restextract / charge.reached_wort) * 100
            context["evg"] = round(EVG_f, 1)
        except TypeError:
            context["evg"] = None
        try:
            # TRE = 0,1808 · Stammwürze [°P] + 0,8192 · SRE [°P]
            TRE = 0.1808 * charge.reached_wort + 0.8192 * charge.restextract

            # Tatsächlicher EVG (%) = (1 - TRE [°P] / Stammwürze [°P]) · 100
            # EVG_t = (1 - TRE / c.reached_wort) * 100
            ALC_v = (
                1
                / 0.79
                * (charge.reached_wort - TRE)
                / (2.0665 - 0.010665 * charge.reached_wort)
            )
            context["alc"] = round(ALC_v, 1)
        except TypeError:
            context["alc"] = None

        if charge.ispindel:
            # TODO: make plots work again
            # context["plot"] = get_plot(c)
            context["plot"] = ""

        else:
            # context["fermentation"] = FermentationProtocol.objects.filter(charge=c.id)
            context["fermentation"] = ""

        # TODO_SIB: host_port = request.META["HTTP_HOST"]
        host_port = "braurat.de:80"
        riddle_id = b64e(("braurat" + str(charge.id)).encode())
        context["qrurl"] = (
            "https://" + host_port + "/public/protocol/" + riddle_id.decode()
        )

        return context

    def processing_pdf(cid):
        logging.debug("processing_pdf")
        # TODO_SIB: for the pdf creation
        """
        c = Charge.objects.get(pk=cid)

        buffer = io.BytesIO()
        pdf = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
            title=str(c) + "_protokoll",
        )

        content = []
        sample_style_sheet = getSampleStyleSheet()
        # if you want to see all the sample styles, this prints them
        sample_style_sheet.list()

        logo = Image(
            os.path.join(BASE_DIR, "static/img/logo-white-long.png"),
            width=384,
            height=80,
        )
        title = Paragraph("Protokoll: " + c.recipe.name, sample_style_sheet["Heading1"])
        p1title = Paragraph("Parameter", sample_style_sheet["Heading2"])

        p1text = []
        p1text.append(
            Paragraph(
                "<u>Braumeister</u>: " + str(c.brewmaster),
                sample_style_sheet["BodyText"],
            )
        )
        p1text.append(
            Paragraph("<u>Charge</u>: " + str(c), sample_style_sheet["BodyText"])
        )
        p1text.append(
            Paragraph(
                "<u>Brautag</u>: " + str(c.production), sample_style_sheet["BodyText"]
            )
        )
        p1text.append(
            Paragraph(
                "<u>Gesamtdauer</u>: " + str(c.duration), sample_style_sheet["BodyText"]
            )
        )
        p1text.append(
            Paragraph("<u>Menge</u>: " + str(c.amount), sample_style_sheet["BodyText"])
        )
        hg = c.amount * c.recipe.hg / AMOUNT_FACTOR
        ng = c.amount * c.recipe.ng / AMOUNT_FACTOR
        p1text.append(
            Paragraph(
                "<u>Wasser</u>: " + str(hg) + " Liter / " + str(ng) + " Liter",
                sample_style_sheet["BodyText"],
            )
        )
        p1text.append(
            Paragraph(
                "<u>Ausstoß</u>: " + str(c.output), sample_style_sheet["BodyText"]
            )
        )
        p1text.append(
            Paragraph(
                "<u>Restextrakt</u>: " + str(c.restextract),
                sample_style_sheet["BodyText"],
            )
        )
        p1text.append(
            Paragraph(
                "<u>Stammwürze</u>: " + str(c.reached_wort),
                sample_style_sheet["BodyText"],
            )
        )
        # calculate evg and alc
        try:
            real_restextract = 0.1808 * c.reached_wort + 0.8192 - c.restextract
            evg = (c.reached_wort - real_restextract) * 100 / c.reached_wort
            alc = (c.reached_wort - real_restextract) / (
                2.0665 - 0.010665 * c.reached_wort
            )
        except ValueError:
            evg = None
            alc = None
        p1text.append(
            Paragraph("<u>EVG</u>: " + str(evg), sample_style_sheet["BodyText"])
        )
        p1text.append(
            Paragraph("<u>Alkohol</u>: " + str(alc), sample_style_sheet["BodyText"])
        )

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
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("ALIGN", (1, 1), (-1, -1), "LEFT"),
            ]
        )

        p2title = Paragraph("Brauprotokoll", sample_style_sheet["Heading2"])
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

        table = Table(data, colWidths=[20, 120, 250, 50])
        table.setStyle(GRID_STYLE)
        content.append(table)

        content.append(PageBreak())

        # Page 3
        p3title = Paragraph("Gärverlauf", sample_style_sheet["Heading2"])
        content.append(p3title)
        if c.ispindel:
            get_plot(c)
            content.append(Image("/tmp/ispindelfig.png"))
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
            table = Table(data, colWidths=[20, 160, 250, 50])
            table.setStyle(GRID_STYLE)
            content.append(table)

        pdf.build(content)
        buffer.seek(0)
        return buffer
        """


class FermentationProtocol(models.Model):
    id = models.AutoField(primary_key=True)
    head = models.ForeignKey(
        FermentationProtocolStep,
        on_delete=models.CASCADE,
        related_name="fermentation_head",
        null=True,
    )
    tail = models.ForeignKey(
        FermentationProtocolStep,
        related_name="fermentation_tail",
        on_delete=models.CASCADE,
        null=True,
    )

    def init(self, charge):
        protocol = charge.fermentation_protocol
        if protocol:
            return protocol
        else:
            charge.fermentation_protocol = self
            charge.save()

    def list(self):
        steps = self.head
        if steps:
            steps = steps.dict().values()
        return steps

    def add_mp(self, mp_form):
        if self.head is None:
            mp = mp_form.save()
            mp.pos = 1
            mp.save()
            self.head = self.tail = mp
        else:
            mp = mp_form.save()
            mp.pos = self.tail.pos + 1
            mp.previous = self.tail
            mp.save()
            mp.previous.next = mp
            mp.previous.save()
            self.tail = mp

        self.save()

    def __str__(self):
        return "[" + str(self.id) + "]"

    def context(self, charge):
        context = {}
        context["charge"] = charge
        context["fermentation"] = self.list()
        context["navi"] = "brewing"
        context["image_url"] = load_dynamic_bg_image()
        context["protocol"] = charge.brew_protocol.list()
        # context["preps"] = PreparationProtocol.objects.filter(charge=c)
        context["preps"] = None
        return context


class RotatedImage(Image):
    def wrap(self, availWidth, availHeight):
        h, w = Image.wrap(self, availHeight, availWidth)
        return w, h

    def draw(self):
        self.canv.rotate(90)
        Image.draw(self)
