from django.db import models

# Create your models here.
class CitySearchCount(models.Model):
    city = models.CharField(max_length=255, unique=True)
    search_count = models.PositiveIntegerField(default=0)