import jinja2

lines = open('templates/dashboard.html', encoding='utf-8').readlines()
snippet = ''.join(lines[230:265])

# Print out lines with their 0-based relative index
for i, l in enumerate(lines[230:265]):
    print(i, l, end='')

try:
    jinja2.Template(snippet)
    print('OK ALL')
except jinja2.exceptions.TemplateSyntaxError as e:
    print('ERROR at line:', e.lineno)
    print(lines[230 + e.lineno - 1])
