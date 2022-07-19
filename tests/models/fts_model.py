from django.db import models
from django.contrib.postgres import indexes, search


__all__ = ("FTSModel",)


class FTSModel(models.Model):
    search_vector = search.SearchVectorField(null=True, default=None)

    class Meta:
        indexes = [
            indexes.GinIndex(fields=["search_vector"], fastupdate=True),
        ]
