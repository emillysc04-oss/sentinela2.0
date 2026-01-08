import os
import smtplib
import requests
from email.message import EmailMessage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup  # Importante para ler o HTML

# --- CONFIGURAÇÕES ---
EMAIL_ORIGEM = os.environ.get('EMAIL_REMETENTE')
SENHA_APP = os.environ.get('SENHA_APP')
EMAIL_DESTINO = EMAIL_ORIGEM

# Palavras que queremos monitorar (Edite conforme necessário)
PALAVRAS_CHAVE = [
    "física médica", 
    "ultrassom", 
    "raio-x", 
    "bolsa de pesquisa", 
    "chamada pública", 
    "edital", 
    "ciências da saúde",
    "fapergs",
    "cnpq"
]

def criar_sessao_robusta():
    """Cria uma sessão que parece um navegador."""
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session

def analisar_site(nome, url, session):
    """Acessa o site e procura as palavras-chave."""
    try:
        resp = session.get(url, timeout=20)
        
        # Se der erro 404 ou 500, avisa
        if resp.status_code != 200:
            return f"⚠️ {nome}: Erro ao acessar (Status {resp.status_code})"

        # Transforma o HTML em texto legível
        soup = BeautifulSoup(resp.content, 'html.parser')
        texto_site = soup.get_text().lower() # Tudo em minúsculo para facilitar busca

        encontradas = []
        for palavra in PALAVRAS_CHAVE:
            if palavra in texto_site:
                encontradas.append(palavra)

        if encontradas:
            return f"✅ {nome}: Encontrei termos de interesse: {', '.join(encontradas)}\n   Link: {url}"
        else:
            return f"ℹ️ {nome}: Site acessado, mas nenhuma palavra-chave encontrada hoje."

    except Exception as e:
        return f"❌ {nome}: Falha na conexão. Erro: {str(e)}"

def executar_sentinela():
    session = criar_sessao_robusta()
    relatorio = []
    
    print("Iniciando varredura...")

    # 1. FAPERGS (Link corrigido para Chamadas Abertas)
    relatorio.append(analisar_site(
        "FAPERGS", 
        "https://fapergs.rs.gov.br/editais-abertos", 
        session
    ))

    # 2. DOU (Diário Oficial - Seção de Pesquisa/Inovação)
    # Nota: O DOU é complexo, vamos olhar a página de pesquisa simples por enquanto
    relatorio.append(analisar_site(
        "DOU (Pesquisa)", 
        "https://www.in.gov.br/leiturajornal", 
        session
    ))

    # Junta o relatório
    texto_final = "\n\n".join(relatorio)
    return texto_final

def enviar_email(corpo_mensagem):
    if not EMAIL_ORIGEM or not SENHA_APP:
        print("Credenciais não configuradas.")
        return

    msg = EmailMessage()
    msg.set_content(f"Olá,\n\nAqui está o resumo da varredura de hoje:\n\n{corpo_mensagem}")
    msg['Subject'] = 'Sentinela: Atualização de Editais'
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
    print(resultado)
    enviar_email(resultado)
