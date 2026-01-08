import os
import smtplib
import requests
from email.message import EmailMessage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS # A novidade: motor de busca

# --- CONFIGURAÇÕES ---
EMAIL_ORIGEM = os.environ.get('EMAIL_REMETENTE')
SENHA_APP = os.environ.get('SENHA_APP')
EMAIL_DESTINO = EMAIL_ORIGEM

# Palavras para verificação em sites fixos (FAPERGS, DOU)
PALAVRAS_CHAVE_FIXAS = ["física médica", "ultrassom", "chamada pública", "edital"]

# Termos para pesquisar na "Internet Geral" (Nacional e Internacional)
# DICA: Use aspas para termos exatos e adicione o ano para filtrar coisas velhas.
TERMOS_DE_BUSCA = [
    '"medical physics" grant 2026', 
    '"ultrasound" research funding 2026',
    'edital "física médica" 2026',
    'bolsa doutorado sanduíche física médica 2026',
    '"medical physics" phd position europe 2026'
]

def criar_sessao_robusta():
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session

def analisar_site_fixo(nome, url, session):
    """Verifica links específicos que você já conhece."""
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return f"⚠️ {nome}: Erro (Status {resp.status_code})"

        soup = BeautifulSoup(resp.content, 'html.parser')
        texto_site = soup.get_text().lower()
        
        encontradas = [p for p in PALAVRAS_CHAVE_FIXAS if p in texto_site]
        
        if encontradas:
            return f"✅ {nome}: Encontrei: {', '.join(encontradas)}\n   Link: {url}"
        return f"ℹ️ {nome}: Nada novo encontrado."
    except Exception as e:
        return f"❌ {nome}: Erro de conexão."

def buscar_na_web():
    """Pesquisa no DuckDuckGo como se fosse um humano."""
    relatorio_busca = []
    relatorio_busca.append("--- RESULTADOS DA BUSCA NA WEB ---")
    
    print("Iniciando buscas na web...")
    
    with DDGS() as ddgs:
        for termo in TERMOS_DE_BUSCA:
            try:
                # Traz os 5 primeiros resultados de cada termo
                results = list(ddgs.text(termo, max_results=5))
                
                if results:
                    relatorio_busca.append(f"\n🔍 Termo: {termo}")
                    for r in results:
                        titulo = r.get('title', 'Sem título')
                        link = r.get('href', '#')
                        # Filtra resultados muito irrelevantes (opcional)
                        relatorio_busca.append(f"   • {titulo}\n     {link}")
                else:
                    relatorio_busca.append(f"\nSearch: {termo} (Sem resultados recentes)")
            except Exception as e:
                relatorio_busca.append(f"Erro ao buscar '{termo}': {str(e)}")
                
    return "\n".join(relatorio_busca)

def executar_sentinela():
    session = criar_sessao_robusta()
    relatorio_final = []
    
    # 1. Checa os sites fixos (FAPERGS/DOU)
    print("Checando sites fixos...")
    relatorio_final.append("--- MONITORAMENTO FIXO ---")
    relatorio_final.append(analisar_site_fixo("FAPERGS", "https://fapergs.rs.gov.br/editais-abertos", session))
    relatorio_final.append(analisar_site_fixo("DOU", "https://www.in.gov.br/leiturajornal", session))
    
    # 2. Faz a busca na Web
    relatorio_final.append("\n" + buscar_na_web())

    return "\n".join(relatorio_final)

def enviar_email(corpo_mensagem):
    if not EMAIL_ORIGEM or not SENHA_APP:
        print("Credenciais ausentes.")
        return

    msg = EmailMessage()
    msg.set_content(corpo_mensagem)
    msg['Subject'] = 'Sentinela: Radar de Editais e Buscas'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = EMAIL_DESTINO

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ORIGEM, SENHA_APP)
            smtp.send_message(msg)
        print("E-mail enviado!")
    except Exception as e:
        print(f"Erro no envio: {e}")

if __name__ == "__main__":
    resultado = executar_sentinela()
    # print(resultado) # Descomente para testar localmente
    enviar_email(resultado)
