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

# DESIGN HCPA (Manual de Identidade Visual)
# Verde Institucional: #009586
# Fonte: Família Sans-Serif Limpa
ESTILO = """
  body { 
    font-family: 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif; 
    background-color: #ffffff; 
    padding: 30px; 
    color: #404040; 
    line-height: 1.6;
  }
  
  .box { 
    max-width: 700px; 
    margin: 0 auto; 
    border-top: 6px solid #009586; 
  }
  
  /* Cabeçalho Centralizado */
  .header { 
    padding: 30px 0; 
    text-align: center; /* Centralizado conforme solicitado */
    border-bottom: 1px solid #eeeeee;
  }
  .header h3 { 
    margin: 0; 
    font-size: 22px; 
    color: #009586; 
    font-weight: 300; 
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .header p {
    margin: 5px 0 0 0;
    font-size: 13px;
    color: #888;
  }
  
  .section { padding: 30px 0; border-bottom: 1px solid #f0f0f0; }
  
  /* Títulos das Seções */
  .section-title { 
    font-size: 12px; 
    font-weight: 700; 
    color: #666; 
    text-transform: uppercase; 
    letter-spacing: 1px;
    margin-bottom: 20px; 
    display: inline-block;
    border-bottom: 2px solid #009586;
    padding-bottom: 5px;
  }
  
  ul { padding: 0; list-style: none; margin: 0; }
  li { margin-bottom: 25px; }
  
  /* Links */
  a { 
    color: #009586; 
    text-decoration: none; 
    font-weight: 600; 
    font-size: 18px;
    display: block;
    margin-bottom: 5px;
  }
  a:hover { text-decoration: underline; }
  
  /* Bloco da IA */
  .ai { 
    font-size: 14px; 
    color: #555; 
    background-color: #f8fcfb; 
    padding: 15px; 
    border-left: 3px solid #009586;
    border-radius: 0 4px 4px 0;
  }
  .label-ai { 
    font-weight: bold; 
    color: #009586; 
    font-size: 10px; 
    text-transform: uppercase; 
    margin-right: 5px;
  }
  
  .pdf-tag { 
    font-size: 10px; 
    color: white; 
    background-color: #009586; 
    padding: 2px 6px; 
    border-radius: 3px; 
    vertical-align: middle; 
    font-weight: bold;
  }
  
  .footer { 
    padding: 40px 0; 
    text-align: center; 
    font-size: 12px; 
    color: #999; 
    border-top: 1px solid #eee;
  }
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
                for r in list(ddgs.text(f'"{tema}" {sufixo_query}', max_results=3)):
                    analise = consultar_ia(r.get('title',''), r.get('body',''))
                    if analise:
                        link = r.get('href','#')
                        pdf = " <span class='pdf-tag'>PDF</span>" if link.endswith('.pdf') else ""
                        html += f"""
                        <li>
                            <a href='{link}'>{r.get('title')} {pdf}</a>
                            <div class='ai'><span class='label-ai'>Análise IA</span> {analise}</div>
                        </li>"""
            except: continue
    return html

if __name__ == "__main__":
    print(">>> Iniciando Varredura HCPA...")
    br = buscar('(edital OR chamada OR seleção OR bolsa) 2025..2026 site:.br')
    world = buscar('(grant OR funding OR phd position) 2025..2026 -site:.br')

    corpo = ""
    if br: corpo += f"<div class='section'><div class='section-title'>Oportunidades Nacionais</div><ul>{br}</ul></div>"
    if world: corpo += f"<div class='section'><div class='section-title'>Oportunidades Internacionais</div><ul>{world}</ul></div>"
    
    if not corpo:
        corpo = "<p style='text-align:center; padding:40px; color:#999; font-size:14px;'>Nenhuma oportunidade relevante encontrada hoje.</p>"

    html_final = f"""
    <html><head><style>{ESTILO}</style></head>
    <body>
        <div class='box'>
            <div class='header'>
                <h3>SISTEMA DE MONITORAMENTO SENTINELA</h3>
                <p>Relatório Diário de Inteligência</p>
            </div>
            {corpo}
            <div class='footer'>
                Hospital de Clínicas de Porto Alegre<br>
                Gerado automaticamente via Inteligência Artificial
            </div>
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
