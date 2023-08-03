from django import template

register = template.Library()


def seconds(td):
    total_seconds = int(td.total_seconds())
    return total_seconds


register.filter("seconds", seconds)
