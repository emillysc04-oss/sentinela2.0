import os, time, smtplib, json, warnings
import google.generativeai as genai
import gspread
from email.message import EmailMessage
from duckduckgo_search import DDGS

# --- 0. LIMPEZA DE LOGS ---
# Ignora avisos de depreciação para não poluir o terminal
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'

# --- 1. CONFIGURAÇÕES ---
EMAIL = os.environ.get('EMAIL_REMETENTE')
SENHA = os.environ.get('SENHA_APP')
KEY = os.environ.get('GEMINI_API_KEY')
SHEETS_JSON = os.environ.get('GOOGLE_CREDENTIALS')

genai.configure(api_key=KEY)
# Forçamos o Gemini a responder SEMPRE em JSON
MODELO = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})

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
            
            # Lê a Coluna C (índice 3)
            valores = sh.sheet1.col_values(3)
            for email in valores:
                if '@' in email and '.' in email:
                    lista_final.append(email.strip())
            print(f">>> Lista carregada: {len(lista_final)} destinatários.")
        except Exception as e:
            print(f"⚠️ Erro Planilha: {e}. Usando modo de segurança.")
    
    if not lista_final: lista_final = [EMAIL]
    return lista_final

DESTINOS = obter_lista_emails()

# --- 3. DESIGN HCPA ---
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

# --- 4. INTELIGÊNCIA EM LOTE ---
def coletar_bruto(sufixo):
    """Coleta tudo o que encontrar no DuckDuckGo."""
    resultados = []
    with DDGS(timeout=30) as ddgs:
        for tema in TEMAS:
            try:
                # Coleta 4 resultados por tema
                for r in list(ddgs.text(f'"{tema}" {sufixo}', max_results=4)):
                    resultados.append(f"Titulo: {r.get('title')} | Link: {r.get('href')} | Resumo: {r.get('body')}")
            except: continue
    return resultados

def curadoria_ia(lista_bruta):
    """Envia a lista para o Gemini filtrar e devolver TUDO o que for bom."""
    if not lista_bruta: return ""
    
    texto_entrada = "\n".join(lista_bruta[:80])
    
    prompt = f"""
    Você é um Editor Sênior do Hospital de Clínicas de Porto Alegre (HCPA).
    Abaixo está uma lista bruta de resultados de busca da web.
    
    SUA MISSÃO:
    Filtrar e selecionar TODAS as oportunidades que sejam RELEVANTES para financiamento, bolsas, editais ou chamadas de pesquisa na área da saúde/tecnologia vigentes (2025/2026).
    
    REGRAS CRÍTICAS:
    1. NÃO limite a quantidade. Se houver 10 relevantes, liste as 10. Se houver 20, liste as 20.
    2. Jogue fora: notícias genéricas, cursos pagos, vendas de produtos ou artigos científicos antigos.
    3. Retorne APENAS um JSON com esta estrutura para cada item aprovado:
       [{{ "titulo": "...", "link": "...", "resumo_ia": "Resumo explicativo em 1 frase." }}]
    
    LISTA BRUTA:
    {texto_entrada}
    """
    
    try:
        resposta = MODELO.generate_content(prompt)
        dados = json.loads(resposta.text)
        
        html_gerado = ""
        for item in dados:
            link = item.get('link','#')
            pdf = " <span class='pdf-tag'>PDF</span>" if link.endswith('.pdf') else ""
            html_gerado += f"""
            <li>
                <a href='{link}'>{item.get('titulo')} {pdf}</a>
                <div class='ai'><span class='label-ai'>Análise Sentinela</span> {item.get('resumo_ia')}</div>
            </li>
            """
        return html_gerado
    except Exception as e:
        print(f"Erro na curadoria IA: {e}")
        return ""

# --- 5. EXECUÇÃO ---
if __name__ == "__main__":
    print(">>> 1. Coletando dados brutos (Brasil)...")
    raw_br = coletar_bruto('(edital OR chamada OR seleção OR bolsa) 2025..2026 site:.br')
    
    print(">>> 2. Coletando dados brutos (Mundo)...")
    raw_world = coletar_bruto('(grant OR funding OR phd position) 2025..2026 -site:.br')

    print(">>> 3. IA Sentinela analisando e filtrando...")
    html_br = curadoria_ia(raw_br)
    html_world = curadoria_ia(raw_world)

    # Monta o corpo do e-mail
    corpo = ""
    if html_br: corpo += f"<div class='section'><div class='section-title'>Oportunidades Nacionais</div><ul>{html_br}</ul></div>"
    if html_world: corpo += f"<div class='section'><div class='section-title'>Oportunidades Internacionais</div><ul>{html_world}</ul></div>"
    
    if not corpo: corpo = "<p style='text-align:center; padding:40px; color:#999;'>Nenhuma oportunidade relevante encontrada hoje.</p>"

    # --- AQUI ESTAVA O ERRO: A variável html_final agora é criada explicitamente ---
    html_final = f"""
    <html><head><style>{ESTILO}</style></head>
    <body>
        <div class='box'>
            <div class='header'>
                <h3>SISTEMA DE MONITORAMENTO SENTINELA</h3>
                <p>Relatório de Inteligência</p>
            </div>
            {corpo}
            <div class='footer'>
                Hospital de Clínicas de Porto Alegre<br>
                Curadoria via IA Generativa
            </div>
        </div>
    </body></html>
    """
    
    print(f">>> Enviando para {len(DESTINOS)} destinatários via Bcc.")
    msg = EmailMessage()
    msg['Subject'], msg['From'], msg['To'] = 'Sistema Sentinela: Relatório Diário', EMAIL, EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
    print("✅ Processo concluído!")
