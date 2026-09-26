# Generated manually for PitchKiln-01 lane no-smoke gear log

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kiln", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LaneGearLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("lane", models.PositiveIntegerField(verbose_name="过道号")),
                ("switchedAt", models.DateTimeField(verbose_name="切换时刻")),
                (
                    "gear",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "1 档"),
                            (2, "2 档"),
                            (3, "3 档"),
                            (4, "4 档"),
                            (5, "5 档"),
                        ],
                        verbose_name="档位",
                    ),
                ),
                (
                    "operatorName",
                    models.CharField(max_length=80, verbose_name="操作人"),
                ),
                (
                    "note",
                    models.CharField(
                        blank=True, default="", max_length=200, verbose_name="备注"
                    ),
                ),
            ],
            options={
                "verbose_name": "过道禁烟档志",
                "verbose_name_plural": "过道禁烟档志",
                "ordering": ["-switchedAt", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="lanegearlog",
            constraint=models.UniqueConstraint(
                fields=("lane", "switchedAt"), name="uniq_lane_gear_log_minute"
            ),
        ),
    ]
