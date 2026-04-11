import jinja2

template = """
          <div class="expiry-alert-item {% if alert.urgent %}expiry-urgent{% endif %}">
            <i class="bi bi-file-earmark-text" style="color:{% if alert.urgent %}#ef4444{% else %}#f59e0b{% endif %};"></i>
            <div style="flex:1;">
              <span style="font-weight:600;font-size:0.875rem;">{{ alert.filename }}</span>
              <span style="font-size:0.78rem;margin-left:0.5rem;color:{% if alert.urgent %}#ef4444{% else %}#f59e0b{% endif %};">
                {% if alert.days == 0 %}Expires TODAY{% elif alert.days == 1 %}Expires tomorrow{% else %}Expires in {{ alert.days }} days{% endif %}
              </span>
            </div>
"""
try:
    jinja2.Template(template)
    print('OK Block 1')
except Exception as e:
    import traceback
    traceback.print_exc()

template2 = """
          <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">
            <i class="bi bi-exclamation-triangle-fill" style="color:#f59e0b;font-size:1.1rem;"></i>
            <strong style="color:#f59e0b;">{{ expiry_alerts|length }} Document{{ 's' if expiry_alerts|length != 1 }} Expiring Soon</strong>
          </div>
"""
try:
    jinja2.Template(template2)
    print('OK Block 2')
except Exception as e:
    import traceback
    traceback.print_exc()
