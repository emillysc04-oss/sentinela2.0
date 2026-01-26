import os, time, smtplib
import google.generativeai as genai
from email.message import EmailMessage
from duckduckgo_search import DDGS

EMAIL = os.environ.get('EMAIL_REMETENTE')
SENHA = os.environ.get('SENHA_APP')
KEY = os.environ.get('GEMINI_API_KEY')
DESTINOS = [e.strip() for e in (os.environ.get('EMAIL_DESTINO') or EMAIL).replace('\n', ',').split(',') if e.strip()]

genai.configure(api_key=KEY)
MODELO = genai.GenerativeModel('gemini-1.5-flash')

ESTILO = """
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; color: #333; }
  .box { background: white; max-width: 700px; margin: 0 auto; border: 1px solid #ddd; border-radius: 5px; overflow: hidden; }
  .header { background: #333; color: white; padding: 20px; text-align: center; letter-spacing: 1px; }
  .header h3 { margin: 0; font-size: 18px; text-transform: uppercase; }
  .section { padding: 25px; border-bottom: 1px solid #eee; }
  .section-title { font-size: 13px; font-weight: bold; color: #444; text-transform: uppercase; margin-bottom: 15px; border-left: 4px solid #0056b3; padding-left: 10px; }
  ul { padding: 0; list-style: none; margin: 0; }
  li { margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #f0f0f0; }
  a { color: #0056b3; text-decoration: none; font-weight: 600; font-size: 15px; }
  .ai { font-size: 12px; color: #555; background: #f9f9f9; padding: 10px; border-radius: 4px; margin-top: 8px; border: 1px solid #eee; }
  .label-ai { font-weight: bold; color: #777; font-size: 10px; text-transform: uppercase; display: block; margin-bottom: 3px; }
  .pdf-tag { font-size: 9px; color: #d32f2f; border: 1px solid #d32f2f; padding: 1px 4px; border-radius: 3px; margin-left: 5px; vertical-align: middle; }
  .footer { background: #f5f5f5; padding: 15px; text-align: center; font-size: 11px; color: #999; border-top: 1px solid #ddd; }
"""

TEMAS = [
    "Radioterapia", "Radiofármacos", "Medicina Nuclear", "Física Médica", "Dosimetria", 
    "Proteção Radiológica", "Inteligência Artificial saúde", "Machine Learning médica", 
    "Deep Learning medicina", "Avaliação de Tecnologias em Saúde", "Inovação Hospitalar", 
    "CNPq", "FAPERGS", "Ministério da Saúde", "Proadi-SUS"]

def consultar_ia(titulo, resumo):
    try: 
        prompt = f"Título: {titulo}\nResumo: {resumo}\nÉ oportunidade acadêmica vigente (2025/2026)? Responda 'NÃO' ou resumo em 1 frase."
        res = MODELO.generate_content(prompt).text.strip()
        return None if "NÃO" in res.upper() or len(res) < 5 else res
    except: return None

def buscar(sufixo_query):
    html = ""
    with DDGS(timeout=30) as ddgs:
        for tema in TEMAS:
            try:
                time.sleep(1.5)
                for r in list(ddgs.text(f'"{tema}" {sufixo_query}', max_results=2)):
                    analise = consultar_ia(r.get('title',''), r.get('body',''))
                    if analise:
                        link = r.get('href','#')
                        pdf = " <span class='pdf-tag'>PDF</span>" if link.endswith('.pdf') else ""
                        html += f"""
                        <li>
                            <a href='{link}'>{r.get('title')}</a>{pdf}
                            <div class='ai'><span class='label-ai'>Análise IA:</span> {analise}</div>
                        </li>"""
            except: continue
    return html

if __name__ == "__main__":
    print(">>> Iniciando Varredura...")
    br = buscar('(edital OR chamada OR seleção OR bolsa) 2025..2026 site:.br')
    world = buscar('(grant OR funding OR phd position) 2025..2026 -site:.br')

    corpo = ""
    if br: corpo += f"<div class='section'><div class='section-title'>BRASIL | Oportunidades Nacionais</div><ul>{br}</ul></div>"
    if world: corpo += f"<div class='section'><div class='section-title'>INTERNACIONAL | Oportunidades Globais</div><ul>{world}</ul></div>"
    
    if not corpo:
        corpo = "<p style='text-align:center; padding:40px; color:#999; font-size:12px;'>Nenhuma oportunidade relevante encontrada hoje.</p>"

    html_final = f"""
    <html><head><style>{ESTILO}</style></head>
    <body>
        <div class='box'>
            <div class='header'><h3>SISTEMA DE MONITORAMENTO SENTINELA</h3></div>
            {corpo}
            <div class='footer'>Relatório Automático Diário</div>
        </div>
    </body></html>
    """
    
    print(f">>> Enviando para: {', '.join(DESTINOS)}")
    msg = EmailMessage()
    msg['Subject'], msg['From'], msg['To'] = 'Sistema Sentinela: Relatório Diário', EMAIL, ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
