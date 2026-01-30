import os, time, smtplib, json, requests, warnings
import google.generativeai as genai
import gspread
from email.message import EmailMessage

# --- 0. CONFIGURAÇÕES ---
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'

EMAIL = os.environ.get('EMAIL_REMETENTE')
SENHA = os.environ.get('SENHA_APP')
KEY = os.environ.get('GEMINI_API_KEY')
SHEETS_JSON = os.environ.get('GOOGLE_CREDENTIALS')
SEARCH_KEY = os.environ.get('GOOGLE_SEARCH_KEY')
SEARCH_CX = os.environ.get('GOOGLE_SEARCH_CX')

# Configuração Gemini
genai.configure(api_key=KEY)
MODELO = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})

# --- 1. LEITURA DA PLANILHA ---
def obter_lista_emails():
    lista = [EMAIL]
    if SHEETS_JSON:
        try:
            credenciais = json.loads(SHEETS_JSON)
            gc = gspread.service_account_from_dict(credenciais)
            try:
                sh = gc.open("Sentinela Emails")
            except:
                sh = gc.open("Formulário sem título (respostas)")
            valores = sh.sheet1.col_values(3)
            validos = [e.strip() for e in valores if '@' in e and '.' in e]
            if validos: lista = validos
            print(f">>> Destinatários carregados: {len(lista)}")
        except Exception as e:
            print(f"⚠️ Erro Planilha: {e}")
    return lista

DESTINOS = obter_lista_emails()

# --- 2. GOOGLE SEARCH API ---
def google_search_api(query):
    print(f"... Buscando: {query}")
    url = "https://www.googleapis.com/customsearch/v1"
    # Como já filtramos os sites no Painel do Google, aqui a busca é ampla
    params = {
        'key': SEARCH_KEY,
        'cx': SEARCH_CX,
        'q': query,
        'num': 10,       # Pega 10 resultados por tema
        'gl': 'br',     
        'hl': 'pt',     
        'dateRestrict': 'm3' # Apenas últimos 3 meses (Super atualizado)
    }
    try:
        resp = requests.get(url, params=params)
        if resp.status_code == 403:
            print("❌ Erro 403: Verifique se a Custom Search API está ATIVADA no Cloud Console.")
            return []
        
        dados = resp.json()
        items = dados.get('items', [])
        resultados = []
        for item in items:
            resultados.append(f"Titulo: {item.get('title')} | Link: {item.get('link')} | Resumo: {item.get('snippet')}")
        return resultados
    except Exception as e:
        print(f"❌ Erro API: {e}")
        return []

# --- 3. ESTRATÉGIA DE BUSCA (SEM 'site:') ---
# O robô agora confia na lista que você configurou no painel
BUSCAS = [
    '"Chamada Pública" "Física Médica" 2025',
    '"Edital" "Radioterapia" "Bolsa" 2025',
    '"Seleção" "Medicina Nuclear" projeto pesquisa',
    '"Grant" "Medical Physics" 2025',
    '"Call for proposals" "Artificial Intelligence" Health',
    '"Edital" "Inovação" Hospitalar 2025'
]

def coletar_dados():
    todos = []
    for query in BUSCAS:
        res = google_search_api(query)
        todos.extend(res)
        time.sleep(1)
    return todos

def filtro_ia(lista_bruta):
    if not lista_bruta: return ""
    lista_unica = list(set(lista_bruta))
    texto_entrada = "\n".join(lista_unica[:150]) # Analisa até 150 links
    
    prompt = f"""
    Você é o Sentinela do HCPA.
    Analise estes resultados da Busca Google (já filtrados por sites oficiais).
    
    MISSÃO:
    Encontre APENAS oportunidades de FOMENTO, BOLSAS ou EDITAIS ABERTOS (2025/2026).
    Áreas: Física Médica, Radioterapia, Med Nuclear, IA em Saúde.
    
    REGRAS:
    1. Ignore notícias, artigos publicados ou eventos passados.
    2. Retorne JSON: [{{ "titulo": "...", "link": "...", "resumo": "..." }}]
    
    DADOS:
    {texto_entrada}
    """
    try:
        resposta = MODELO.generate_content(prompt)
        dados = json.loads(resposta.text)
        html = ""
        for item in dados:
            html += f"""
            <li style='margin-bottom:15px; border-bottom:1px solid #eee; padding-bottom:10px;'>
                <a href='{item.get('link')}' style='color:#009586;font-weight:bold;text-decoration:none;font-size:16px;'>
                    {item.get('titulo')} 
                    <span style='font-size:10px;background:#009586;color:white;padding:2px 5px;border-radius:3px;'>VERIFICADO</span>
                </a>
                <div style='font-size:13px;color:#555;margin-top:5px;'>{item.get('resumo')}</div>
            </li>"""
        return html
    except: return ""

# --- 4. EXECUÇÃO ---
if __name__ == "__main__":
    raw_data = coletar_dados()
    print(f">>> {len(raw_data)} resultados oficiais encontrados.")
    
    html_conteudo = filtro_ia(raw_data)
    
    if not html_conteudo:
        html_conteudo = "<p style='text-align:center;color:#999;padding:40px;'>Nenhuma oportunidade nova encontrada hoje.</p>"

    html_final = f"""
    <html><body style='font-family:Segoe UI, sans-serif; background:#fff; padding:20px;'>
        <div style='max-width:700px; margin:0 auto; border-top:6px solid #009586;'>
            <div style='text-align:center; padding:20px; border-bottom:1px solid #eee;'>
                <h3 style='color:#009586; margin:0;'>SENTINELA HCPA</h3>
                <p style='color:#777; font-size:12px;'>Monitoramento Oficial Governamental</p>
            </div>
            <ul style='list-style:none; padding:20px 0;'>{html_conteudo}</ul>
            <div style='text-align:center; font-size:11px; color:#aaa; border-top:1px solid #eee; padding:20px;'>
                Hospital de Clínicas de Porto Alegre
            </div>
        </div>
    </body></html>
    """
    
    print(f">>> Enviando para {len(DESTINOS)} pessoas.")
    msg = EmailMessage()
    msg['Subject'] = 'Sentinela: Relatório Oficial (Google Gov)'
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
    print("✅ Sucesso!")
