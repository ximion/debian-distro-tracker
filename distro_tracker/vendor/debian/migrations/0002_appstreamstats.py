# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_keywords_descriptions'),
        ('debian', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppStreamStats',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('stats', jsonfield.fields.JSONField(default=dict)),
                ('package', models.OneToOneField(related_name='appstream_stats', to='core.PackageName')),
            ],
        ),
    ]
