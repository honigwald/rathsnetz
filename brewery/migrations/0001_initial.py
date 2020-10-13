# Generated by Django 3.1.1 on 2020-10-07 16:49

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Charge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.IntegerField()),
                ('production', models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name='IngredientStorage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('amount', models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('creation', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name='Type',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='Unit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='Step',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('step', models.IntegerField()),
                ('title', models.CharField(max_length=50)),
                ('description', models.CharField(max_length=200)),
                ('duration', models.DurationField(blank=True, null=True)),
                ('amount', models.FloatField(blank=True, null=True)),
                ('ingredient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='brewery.ingredientstorage')),
                ('recipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='brewery.recipe')),
            ],
        ),
        migrations.CreateModel(
            name='Protocol',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('step', models.IntegerField()),
                ('title', models.CharField(max_length=50)),
                ('description', models.CharField(max_length=200)),
                ('duration', models.DurationField(blank=True, null=True)),
                ('ingredient', models.CharField(max_length=200)),
                ('amount', models.FloatField(blank=True, null=True)),
                ('tstart', models.TimeField()),
                ('tend', models.TimeField()),
                ('comment', models.CharField(max_length=200)),
                ('charge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='brewery.charge')),
            ],
        ),
        migrations.AddField(
            model_name='ingredientstorage',
            name='type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='brewery.type'),
        ),
        migrations.AddField(
            model_name='ingredientstorage',
            name='unit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='brewery.unit'),
        ),
        migrations.CreateModel(
            name='Fermentation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('temperature', models.FloatField()),
                ('fermentation', models.FloatField()),
                ('date', models.DateTimeField()),
                ('charge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='brewery.charge')),
            ],
        ),
        migrations.AddField(
            model_name='charge',
            name='recipe',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='brewery.recipe'),
        ),
        migrations.CreateModel(
            name='BeerStorage',
            fields=[
                ('keg_nr', models.AutoField(primary_key=True, serialize=False)),
                ('status', models.CharField(default='empty', max_length=200)),
                ('volume', models.IntegerField()),
                ('filling', models.DateTimeField(blank=True, null=True)),
                ('content', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='brewery.charge')),
            ],
        ),
    ]