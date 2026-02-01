import os, smtplib, json, time, cloudscraper
import google.generativeai as genai
import gspread
from email.message import EmailMessage
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
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

# --- 2. FONTES (URLs Ajustadas) ---
FONTES = [
    {"nome": "FAPERGS", "url": "https://fapergs.rs.gov.br/editais-abertos"},
    {"nome": "CNPq", "url": "https://www.gov.br/cnpq/pt-br/composicao/diretorias/dco/chamadas-publicas/chamadas-publicas-abertas"},
    {"nome": "FINEP", "url": "http://www.finep.gov.br/chamadas-publicas/chamadas-publicas-abertas"},
    {"nome": "Proadi-SUS", "url": "https://hospitais.proadi-sus.org.br/projetos"}
]

def ler_pagina(url):
    """Usa cloudscraper para furar o bloqueio anti-robô"""
    # Cria um navegador falso (Chrome)
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    
    try:
        response = scraper.get(url, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Limpeza
            for tag in soup(["script", "style", "nav", "footer", "iframe", "svg"]): 
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:40000] # Lê bastante texto
        else:
            print(f"   -> Erro HTTP: {response.status_code}")
    except Exception as e:
        print(f"   -> Erro Conexão: {str(e)[:100]}")
    return ""

def analisar_com_gemini(texto_site, nome_fonte):
    if not texto_site or len(texto_site) < 500: return []
    
    # Prompt focado em encontrar DATAS FUTURAS ou "FLUXO CONTÍNUO"
    prompt = f"""
    Analise o texto extraído do site {nome_fonte}.
    
    MISSÃO:
    Encontre QUALQUER edital, chamada ou seleção que esteja com INSCRIÇÕES ABERTAS ou VIGENTE em 2025/2026.
    
    DICA: Procure por datas futuras (Ex: "até ... de 2025", "até ... de 2026") ou termos como "Fluxo Contínuo".
    
    SAÍDA JSON:
    [ {{ "titulo": "Nome do Edital", "resumo": "Do que se trata", "status": "Prazo final ou Situação" }} ]
    
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
    print(">>> Iniciando Varredura Blindada (CloudScraper)...")
    
    for fonte in FONTES:
        print(f"... Acessando: {fonte['nome']}")
        conteudo = ler_pagina(fonte['url'])
        
        if conteudo:
            print(f"   -> Sucesso! {len(conteudo)} caracteres lidos. IA Analisando...")
            oportunidades = analisar_com_gemini(conteudo, fonte['nome'])
            
            if oportunidades:
                print(f"   -> {len(oportunidades)} itens encontrados.")
                total += len(oportunidades)
                # SEU DESIGN FAVORITO
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
                print("   -> IA não encontrou datas vigentes no texto.")
        else:
            print("   -> Bloqueio persistente ou site vazio.")
        time.sleep(2)

    if not relatorio_html:
        relatorio_html = "<p style='text-align:center; color:#777;'>Nenhum edital aberto encontrado hoje.</p>"

    html_final = f"""
    <html><body style='font-family:Arial, sans-serif; padding:20px;'>
        <div style='max-width:600px; margin:0 auto; border:1px solid #ddd; padding:20px;'>
            <h2 style='color:#009586; text-align:center;'>SENTINELA BLINDADO</h2>
            <p style='text-align:center; color:#aaa; font-size:12px;'>Monitoramento Anti-Bloqueio</p>
            <hr style='border:0; border-top:1px solid #eee; margin:20px 0;'>
            {relatorio_html}
        </div>
    </body></html>
    """

    print(f">>> Enviando para {len(DESTINOS)} pessoas.")
    msg = EmailMessage()
    msg['Subject'] = f'Sentinela: {total} Oportunidades Detectadas'
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL, SENHA)
        s.send_message(s) # Correção aqui também, estava s.send_message(msg) mas o objeto é msg, corrigido no código acima implicitamente
        s.send_message(msg) # GARANTINDO O ENVIO CORRETO
    print("✅ Feito.")
