# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-02 19:23
from __future__ import unicode_literals

from django.db import migrations, models
import djchoices.choices


class Migration(migrations.Migration):

    dependencies = [
        ('refrigerator', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='recipe',
            name='title',
            field=models.CharField(default='', max_length=200),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='foodtype',
            name='unit',
            field=models.PositiveIntegerField(choices=[(1, 'Gram'), (2, 'Kilogram'), (3, 'Liter'), (4, 'Box'), (5, 'Package')], validators=[djchoices.choices.ChoicesValidator({1: 'Gram', 2: 'Kilogram', 3: 'Liter', 4: 'Box', 5: 'Package'})]),
        ),
    ]
