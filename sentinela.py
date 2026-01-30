import os, time, smtplib, json
import google.generativeai as genai
import gspread
from email.message import EmailMessage
from duckduckgo_search import DDGS

# --- 1. CONFIGURAÇÕES ---
EMAIL = os.environ.get('EMAIL_REMETENTE')
SENHA = os.environ.get('SENHA_APP')
KEY = os.environ.get('GEMINI_API_KEY')
SHEETS_JSON = os.environ.get('GOOGLE_CREDENTIALS')

genai.configure(api_key=KEY)
MODELO = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. FUNÇÃO DE LISTA DE E-MAILS ---
def obter_lista_emails():
    lista_final = []
    if SHEETS_JSON:
        try:
            credenciais = json.loads(SHEETS_JSON)
            gc = gspread.service_account_from_dict(credenciais)
            try:
                sh = gc.open("Sentinela Emails")
            except:
                sh = gc.open("Formulário sem título (respostas)")
            
            valores = sh.sheet1.col_values(3)
            for email in valores:
                if '@' in email and '.' in email:
                    lista_final.append(email.strip())
            print(f">>> Planilha carregada: {len(lista_final)} destinatários.")
        except Exception as e:
            print(f"⚠️ Erro Planilha: {e}. Usando modo segurança.")
    
    if not lista_final: lista_final = [EMAIL]
    return lista_final

#DESTINOS = obter_lista_emails()
DESTINOS = EMAIL
# --- 3. DESIGN HCPA (Identidade Visual) ---
ESTILO = """
  body { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background: #fff; padding: 30px; color: #404040; line-height: 1.6; }
  .box { max-width: 700px; margin: 0 auto; border-top: 6px solid #009586; }
  .header { padding: 30px 0; text-align: center; border-bottom: 1px solid #eee; }
  .header h3 { margin: 0; font-size: 22px; color: #009586; font-weight: 300; letter-spacing: 0.5px; text-transform: uppercase; }
  .section { padding: 30px 0; border-bottom: 1px solid #f0f0f0; }
  .section-title { font-size: 12px; font-weight: 700; color: #666; text-transform: uppercase; border-bottom: 2px solid #009586; padding-bottom: 5px; }
  ul { padding: 0; list-style: none; }
  li { margin-bottom: 25px; }
  a { color: #009586; text-decoration: none; font-weight: 600; font-size: 18px; display: block; }
  .ai { font-size: 14px; color: #555; background: #f8fcfb; padding: 15px; border-left: 3px solid #009586; margin-top: 5px; }
  .label-ai { font-weight: bold; color: #009586; font-size: 10px; text-transform: uppercase; }
  .pdf-tag { font-size: 10px; color: white; background: #009586; padding: 2px 6px; border-radius: 3px; vertical-align: middle; }
  .footer { padding: 40px 0; text-align: center; font-size: 12px; color: #999; border-top: 1px solid #eee; }
"""

TEMAS = [
    "Radioterapia", "Radiofármacos", "Medicina Nuclear", "Física Médica", "Dosimetria", 
    "Proteção Radiológica", "Inteligência Artificial saúde", "Inovação Hospitalar", 
    "CNPq", "FAPERGS", "Ministério da Saúde", "Proadi-SUS"
]

# --- 4. INTELIGÊNCIA INDIVIDUAL (PENTE FINO) ---
def consultar_ia(titulo, resumo):
    """Analisa UM item por vez. Se for bom, resume. Se for lixo, descarta."""
    try: 
        prompt = f"""
        Analise este resultado de busca:
        Título: {titulo}
        Resumo: {resumo}
        
        PERGUNTA: Isto é uma oportunidade de financiamento, bolsa, edital ou chamada de pesquisa na área da saúde/tecnologia vigente (2025 ou 2026)?
        
        REGRAS:
        - Responda "NÃO" para: notícias, artigos científicos já publicados, cursos pagos, ou coisas antigas.
        - Se for RELEVANTE, escreva um resumo de 1 frase explicando o que é.
        """
        res = MODELO.generate_content(prompt).text.strip()
        # Se a IA disser NÃO, retornamos vazio (o item será ignorado)
        return None if "NÃO" in res.upper() or len(res) < 5 else res
    except: return None

def buscar(sufixo_query):
    html = ""
    with DDGS(timeout=30) as ddgs:
        for tema in TEMAS:
            try:
                # Pausa para não bloquear a API do Google (importante no método pente fino)
                time.sleep(2) 
                
                # Aumentei para 4 resultados POR TEMA. 
                # Se temos 12 temas x 4 resultados = 48 itens verificados toda manhã.
                for r in list(ddgs.text(f'"{tema}" {sufixo_query}', max_results=4)):
                    
                    analise = consultar_ia(r.get('title',''), r.get('body',''))
                    
                    if analise: # Só entra na lista se a IA aprovou
                        link = r.get('href','#')
                        pdf = " <span class='pdf-tag'>PDF</span>" if link.endswith('.pdf') else ""
                        html += f"""
                        <li>
                            <a href='{link}'>{r.get('title')} {pdf}</a>
                            <div class='ai'><span class='label-ai'>Análise Sentinela</span> {analise}</div>
                        </li>"""
            except: continue
    return html

# --- 5. EXECUÇÃO ---
if __name__ == "__main__":
    print(">>> Iniciando Varredura Detalhada (Pente Fino)...")
    
    # Buscas (Brasil e Mundo)
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
                Monitoramento Automatizado
            </div>
        </div>
    </body></html>
    """
    
    print(f">>> Enviando para {len(DESTINOS)} destinatários via Bcc.")
    
    msg = EmailMessage()
    msg['Subject'] = 'Sistema Sentinela: Relatório Diário'
    msg['From'] = EMAIL
    msg['To'] = EMAIL 
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
    print("✅ E-mail enviado!")
