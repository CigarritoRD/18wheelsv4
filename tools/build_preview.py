"""Build the self-contained, explicitly local-only demonstration."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'app/static/index.html').read_text()
css=(ROOT/'app/static/style.css').read_text()
app=(ROOT/'app/static/app.js').read_text()
adapter=(ROOT/'tools/demo-adapter.js').read_text()
# A demo never pretends to provide real authentication.
app=app.replace("logout:async()=>{await api('/api/logout'", "logout:async()=>{if(DEMO){toast('This demo has no real sign-in. Use the Admin, Technician, and Requester buttons to switch roles.');return;}await api('/api/logout'")
html=html.replace('<link rel="stylesheet" href="/static/style.css">','<style>'+css+'</style>')
html=html.replace('<script defer src="/static/app.js"></script>','')
html=html.replace('</body>','<script>'+adapter+'</script><script>'+app+'</script></body>')
html=html.replace('<title>18wheelers | Jobs</title>','<title>18wheelers | Interactive Demo</title>')
output=ROOT/'18wheelers-preview.html'
output.write_text(html)
print(output)
