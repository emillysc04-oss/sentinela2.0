import os
import smtplib
import requests
from email.message import EmailMessage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURAÇÕES ---
EMAIL_ORIGEM = os.environ.get('EMAIL_REMETENTE')
SENHA_APP = os.environ.get('SENHA_APP')
EMAIL_DESTINO = EMAIL_ORIGEM  # Ou mude para outro e-mail se quiser

def criar_sessao_robusta():
    """Cria uma sessão que parece um navegador e tenta de novo se falhar."""
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    # O 'User-Agent' é a chave para não tomar erro 104/ConnectionReset
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session

def verificar_sites():
    session = criar_sessao_robusta()
    relatorio = []
    
    # 1. Teste FAPERGS (Exemplo)
    try:
        url_fapergs = "https://fapergs.rs.gov.br/editais" # Exemplo
        resp = session.get(url_fapergs, timeout=15)
        if resp.status_code == 200:
            relatorio.append(f"✅ FAPERGS acessada com sucesso (Status 200).")
            # AQUI VOCÊ COLOCA SUA LÓGICA DE BUSCAR PALAVRAS CHAVE (BeautifulSoup)
        else:
            relatorio.append(f"⚠️ FAPERGS retornou erro: {resp.status_code}")
    except Exception as e:
        relatorio.append(f"❌ Erro ao acessar FAPERGS: {str(e)}")

    # 2. Teste DOU (Exemplo)
    try:
        url_dou = "https://www.in.gov.br/leiturajornal"
        resp = session.get(url_dou, timeout=15)
        if resp.status_code == 200:
            relatorio.append(f"✅ DOU acessado com sucesso (Status 200).")
        else:
            relatorio.append(f"⚠️ DOU retornou erro: {resp.status_code}")
    except Exception as e:
        relatorio.append(f"❌ Erro ao acessar DOU: {str(e)}")

    return "\n".join(relatorio)

def enviar_email(corpo_mensagem):
    if not EMAIL_ORIGEM or not SENHA_APP:
        print("ERRO: As credenciais de e-mail não foram configuradas nas variáveis de ambiente.")
        return

    msg = EmailMessage()
    msg.set_content(corpo_mensagem)
    msg['Subject'] = 'Relatório do Sentinela'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = EMAIL_DESTINO

    try:
        # Conexão segura com Gmail
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ORIGEM, SENHA_APP)
            smtp.send_message(msg)
        print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

if __name__ == "__main__":
    print("Iniciando Sentinela...")
    resultado = verificar_sites()
    print("Resultado da verificação:")
    print(resultado)
    enviar_email(resultado)
