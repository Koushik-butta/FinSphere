import jinja2

template = """
{{ 's' if expiry_alerts|length != 1 }}
"""
try:
    print('Testing template:', jinja2.Template(template).render(expiry_alerts=["test"]))
except Exception as e:
    import traceback
    traceback.print_exc()
