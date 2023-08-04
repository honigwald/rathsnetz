from django.db import models
from .preparation import Preparation
from .step import ProtocolBrewStep, ProtocolFermentationStep

class FermentationProtocol(models.Model):
    id = models.AutoField(primary_key=True)
    head = models.ForeignKey(ProtocolFermentationStep, on_delete=models.CASCADE, blank=True, null=True)

    def list(self):
        return self.head.list()

    def __str__(self):
        return "[" + str(self) + "] " + str(self.step)

    
class BrewProtocol(models.Model):
    id = models.AutoField(primary_key=True)
    head = models.ForeignKey(ProtocolBrewStep, on_delete=models.CASCADE, blank=True, null=True)

    def list(self):
        return self.head.list()

    def __str__(self):
        return str(self.id) + "." + str(self.step)
    

class PreparationProtocol(models.Model):
    id = models.AutoField(primary_key=True)
    preparation = models.ForeignKey(Preparation, on_delete=models.DO_NOTHING)
    done = models.BooleanField()

    def __str__(self):
        return str(self.id) + "_" + str(self.preparation.short)
