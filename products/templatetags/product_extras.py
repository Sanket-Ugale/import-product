from django import template

register = template.Library()


@register.filter
def percentage(value, total):
    """
    Calculate percentage with proper handling of edge cases.
    Usage: {{ value|percentage:total }}
    Returns percentage with 2 decimal places for better accuracy.
    """
    try:
        if not total or total == 0:
            return "0.00"
        if not value:
            return "0.00"
        percent = (value / total) * 100
        # Show 2 decimal places for better accuracy
        return f"{percent:.2f}"
    except (ValueError, ZeroDivisionError, TypeError):
        return "0.00"

