import os, smtplib, json, time, requests, urllib3
import google.generativeai as genai
import gspread
from email.message import EmailMessage
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EMAIL = os.environ.get('EMAIL_REMETENTE')
SENHA = os.environ.get('SENHA_APP')
KEY = os.environ.get('GEMINI_API_KEY')
SHEETS_JSON = os.environ.get('GOOGLE_CREDENTIALS')

genai.configure(api_key=KEY)
MODELO = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})

# --- 1. LISTA DE E-MAILS ---
def obter_destinatarios():
    lista = [EMAIL]
    if SHEETS_JSON:
        try:
            credenciais = json.loads(SHEETS_JSON)
            gc = gspread.service_account_from_dict(credenciais)
            try: sh = gc.open("Sentinela Emails")
            except: sh = gc.open("Formulário sem título (respostas)")
            vals = sh.sheet1.col_values(3)
            validos = [e.strip() for e in vals if '@' in e and '.' in e and 'email' not in e.lower()]
            if validos: lista = validos
            print(f">>> Destinatários: {len(lista)}")
        except: pass
    return lista

DESTINOS = obter_destinatarios()

# --- 2. FONTES (MODO RSS/NOTÍCIAS) ---
# Mudamos para páginas de Notícias/RSS que são mais fáceis de ler que os painéis de editais
FONTES = [
    {
        "nome": "CNPq (Notícias)", 
        "url": "https://www.gov.br/cnpq/pt-br/assuntos/noticias" 
    },
    {
        "nome": "FINEP (Imprensa)", 
        "url": "http://www.finep.gov.br/noticias"
    },
    {
        "nome": "FAPERGS (Feed)", 
        "url": "https://fapergs.rs.gov.br/noticias" # Tentativa na página de notícias em vez de editais
    },
    {
        "nome": "Proadi-SUS", 
        "url": "https://hospitais.proadi-sus.org.br/novidades"
    }
]

def ler_pagina(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        # verify=False ajuda a passar por alguns firewalls gov.br
        response = requests.get(url, headers=headers, timeout=25, verify=False)
        response.encoding = 'utf-8' # Força UTF-8 para corrigir acentos
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # --- DEBUG: O QUE O ROBÔ ESTÁ VENDO? ---
            titulo_site = soup.title.string.strip() if soup.title else "Sem Título"
            print(f"   -> Site acessado: '{titulo_site}'") 
            # ---------------------------------------

            # Limpa o HTML
            for tag in soup(["script", "style", "nav", "footer", "iframe", "header", "svg"]): 
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:50000] 
        else:
            print(f"   -> Erro HTTP: {response.status_code}")
    except Exception as e:
        print(f"   -> Erro Conexão: {str(e)[:100]}")
    return ""

def analisar_com_gemini(texto_site, nome_fonte):
    if not texto_site or len(texto_site) < 500: return []
    
    prompt = f"""
    Analise o texto desta página de notícias/editais: {nome_fonte}.
    
    MISSÃO:
    Identifique QUALQUER oportunidade de fomento, chamada pública, edital ou bolsa mencionada.
    Se encontrar menções a "Aberto", "Lançado", "Inscrições", traga para o relatório.
    
    IMPORTANTE: 
    Não filtre rigorosamente por data. Se parecer recente (últimos meses), inclua.
    
    SAÍDA JSON:
    [ {{ "titulo": "Título da Notícia/Edital", "resumo": "Do que se trata", "status": "Situação aparente" }} ]
    
    TEXTO:
    {texto_site}
    """
    try:
        resp = MODELO.generate_content(prompt)
        return json.loads(resp.text.replace('```json', '').replace('```', ''))
    except: return []

# --- 3. EXECUÇÃO ---
if __name__ == "__main__":
    relatorio_html = ""
    total = 0
    print(">>> Iniciando Sentinela 56.0 (Estratégia Notícias)...")
    
    for fonte in FONTES:
        print(f"... Verificando: {fonte['nome']}")
        conteudo = ler_pagina(fonte['url'])
        
        if conteudo:
            print(f"   -> Texto extraído ({len(conteudo)} caracteres). IA Analisando...")
            oportunidades = analisar_com_gemini(conteudo, fonte['nome'])
            
            if oportunidades:
                print(f"   -> {len(oportunidades)} itens relevantes.")
                total += len(oportunidades)
                
                # SEU DESIGN FAVORITO (CINZA COM BORDA VERDE)
                relatorio_html += f"<div style='margin-bottom:25px; padding:15px; background:#f9f9f9; border-left:4px solid #009586;'>"
                relatorio_html += f"<h3 style='margin-top:0; color:#005f56;'>📍 {fonte['nome']}</h3><ul style='padding-left:20px;'>"
                for item in oportunidades:
                    relatorio_html += f"""
                    <li style='margin-bottom:10px;'>
                        <strong>{item.get('titulo')}</strong><br>
                        <span style='color:#555;'>{item.get('resumo')}</span><br>
                        <span style='font-size:12px; font-weight:bold; color:#d32f2f;'>{item.get('status')}</span>
                    </li>"""
                relatorio_html += "</ul></div>"
            else:
                print("   -> IA leu, mas não achou termos de editais recentes.")
        else:
            print("   -> Falha total na leitura do site.")
        time.sleep(2)

    if not relatorio_html:
        relatorio_html = "<p style='text-align:center; color:#777;'>Nenhuma oportunidade encontrada nas notícias recentes.</p>"

    html_final = f"""
    <html><body style='font-family:Arial, sans-serif; padding:20px;'>
        <div style='max-width:600px; margin:0 auto; border:1px solid #ddd; padding:20px;'>
            <h2 style='color:#009586; text-align:center;'>SENTINELA OFICIAL</h2>
            <p style='text-align:center; color:#aaa; font-size:12px;'>Monitoramento de Notícias & Editais</p>
            <hr style='border:0; border-top:1px solid #eee; margin:20px 0;'>
            {relatorio_html}
        </div>
    </body></html>
    """

    print(f">>> Enviando e-mail para {len(DESTINOS)} pessoas.")
    msg = EmailMessage()
    msg['Subject'] = f'Sentinela: {total} Oportunidades (Varredura Notícias)'
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
    print("✅ E-mail enviado!")
