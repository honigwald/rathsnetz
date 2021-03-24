from django import template

register = template.Library()


def seconds(td):
    total_seconds = int(td.total_seconds())
    print("duration: filter")
    print("{}".format(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    return total_seconds


register.filter('seconds', seconds)
