import os, time, smtplib, json, requests, warnings, logging
import google.generativeai as genai
import gspread
from email.message import EmailMessage
from google.oauth2.service_account import Credentials

# --- 0. SILENCIAR AVISOS ---
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'
logging.getLogger('googleapiclient').setLevel(logging.ERROR)

# --- 1. CONFIGURAÇÕES ---
EMAIL = os.environ.get('EMAIL_REMETENTE')
SENHA = os.environ.get('SENHA_APP')
KEY = os.environ.get('GEMINI_API_KEY')
SHEETS_JSON = os.environ.get('GOOGLE_CREDENTIALS')
SEARCH_KEY = os.environ.get('GOOGLE_SEARCH_KEY')
SEARCH_CX = os.environ.get('GOOGLE_SEARCH_CX')

genai.configure(api_key=KEY)
MODELO = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})

# --- 2. LEITURA DA PLANILHA ---
def obter_lista_emails():
    lista = [EMAIL]
    if SHEETS_JSON:
        try:
            # Escopos necessários para evitar erro de permissão na planilha
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            info_conta = json.loads(SHEETS_JSON)
            creds = Credentials.from_service_account_info(info_conta, scopes=scopes)
            gc = gspread.authorize(creds)
            try:
                sh = gc.open("Sentinela Emails")
            except:
                sh = gc.open("Formulário sem título (respostas)")
            valores = sh.sheet1.col_values(3)
            validos = [e.strip() for e in valores if '@' in e and '.' in e]
            if validos: lista = validos
            print(f">>> Planilha OK: {len(lista)} e-mails.")
        except Exception as e:
            print(f"⚠️ Aviso Planilha (Usando backup): {e}")
    return lista

DESTINOS = obter_lista_emails()

# --- 3. GOOGLE SEARCH API (COM DIAGNÓSTICO REAL) ---
def google_search_api(query):
    print(f"... Google: {query}")
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'key': SEARCH_KEY,
        'cx': SEARCH_CX,
        'q': query,
        'num': 8,
        'gl': 'br',
        'hl': 'pt',
        'dateRestrict': 'm3'
    }
    try:
        resp = requests.get(url, params=params)
        
        # AGORA SIM VAMOS VER O MOTIVO REAL DO ERRO
        if resp.status_code == 403:
            print(f"❌ ERRO 403 REAL: {resp.json().get('error', {}).get('message')}")
            return []
            
        if resp.status_code != 200:
            print(f"❌ Erro API ({resp.status_code}): {resp.text}")
            return []
        
        return [f"Titulo: {i.get('title')} | Link: {i.get('link')} | Resumo: {i.get('snippet')}" for i in resp.json().get('items', [])]
    except Exception as e:
        print(f"❌ Erro Conexão: {e}")
        return []

# --- 4. BUSCAS ---
BUSCAS = [
    'site:gov.br "Chamada Pública" "Física Médica" 2025',
    'site:gov.br/cnpq "Chamadas Abertas" 2025',
    'site:fapergs.rs.gov.br "Editais Abertos" 2025',
    '"Edital" "Radioterapia" "Bolsa" vigente 2025',
    'site:proadi-sus.org.br "Edital" seleção'
]

def coletar_dados():
    todos = []
    if not SEARCH_KEY or not SEARCH_CX:
        print("❌ ERRO: Faltam as chaves de busca no GitHub Secrets!")
        return []
    for query in BUSCAS:
        todos.extend(google_search_api(query))
        time.sleep(1)
    return todos

def filtro_ia(lista_bruta):
    if not lista_bruta: return ""
    prompt = f"""
    Você é o Auditor de Editais do HCPA.
    Analise os resultados do Google abaixo.
    MISSÃO: Selecione APENAS editais/bolsas ABERTOS (2025/2026) em Física Médica, Radioterapia, IA em Saúde.
    Retorne JSON: [{{ "titulo": "...", "link": "...", "resumo": "..." }}]
    DADOS: {str(lista_bruta)[:8000]}
    """
    try:
        return json.loads(MODELO.generate_content(prompt).text)
    except: return []

# --- 5. EXECUÇÃO ---
if __name__ == "__main__":
    raw = coletar_dados()
    if raw:
        print(f">>> {len(raw)} itens encontrados. Analisando...")
        dados = filtro_ia(raw)
        if dados:
            html = "".join([f"<li><a href='{d['link']}'><b>{d['titulo']}</b></a><br>{d['resumo']}</li>" for d in dados])
            msg = EmailMessage()
            msg['Subject'] = 'Sentinela: Relatório Oficial'
            msg['From'] = EMAIL
            msg['Bcc'] = ', '.join(DESTINOS)
            msg.add_alternative(f"<ul>{html}</ul>", subtype='html')
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
                s.login(EMAIL, SENHA)
                s.send_message(msg)
            print("✅ E-mail enviado com sucesso!")
        else: print(">>> IA não encontrou editais relevantes nos resultados.")
    else: print(">>> Falha na busca (ver erro 403 acima).")
