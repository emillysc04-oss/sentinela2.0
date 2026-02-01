import os, smtplib, json, requests, time, urllib3
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
        except Exception as e: print(f">>> Erro Planilha: {str(e)[:50]}")
    return lista

DESTINOS = obter_destinatarios()

# --- 2. FONTES ---
FONTES = [
    {"nome": "FAPERGS", "url": "https://fapergs.rs.gov.br/editais-abertos"},
    {"nome": "CNPq", "url": "https://www.gov.br/cnpq/pt-br/composicao/diretorias/dco/chamadas-publicas/chamadas-publicas-abertas"},
    {"nome": "FINEP", "url": "http://www.finep.gov.br/chamadas-publicas/chamadas-publicas-abertas"},
    {"nome": "Proadi-SUS", "url": "https://hospitais.proadi-sus.org.br/projetos"}
]

def ler_pagina(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Upgrade-Insecure-Requests': '1'}
    try:
        response = requests.get(url, headers=headers, timeout=25, verify=False)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer", "header", "iframe"]): tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:35000]
    except Exception as e: print(f"   -> Erro: {str(e)[:50]}")
    return ""

def analisar_com_gemini(texto_site, nome_fonte):
    if not texto_site: return []
    
    # PROMPT "ARRASTÃO" (Traz tudo que for dinheiro/bolsa)
    prompt = f"""
    Analise o texto do site {nome_fonte}.
    
    MISSÃO:
    Liste TODAS as oportunidades de financiamento, bolsas ou editais que pareçam estar ABERTOS ou VIGENTES (mesmo que sem data explícita).
    
    NÃO FILTRE POR TEMA. Traga tudo o que encontrar sobre:
    - Chamadas Universais
    - Bolsas (qualquer tipo)
    - Projetos de Pesquisa
    - Apoio a Eventos ou Inovação
    
    SAÍDA JSON:
    [ {{ "titulo": "...", "resumo": "...", "status": "..." }} ]
    
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
    print(">>> Iniciando Varredura 'ARRASTÃO'...")
    
    for fonte in FONTES:
        print(f"... Lendo: {fonte['nome']}")
        conteudo = ler_pagina(fonte['url'])
        
        if conteudo:
            # DEBUG: Mostra o que ele leu pra você ter certeza
            print(f"   -> Site lido! Início do texto: {conteudo[:100]}...") 
            print("   -> IA analisando...")
            
            oportunidades = analisar_com_gemini(conteudo, fonte['nome'])
            
            if oportunidades:
                print(f"   -> {len(oportunidades)} itens encontrados.")
                total += len(oportunidades)
                # SEU DESIGN FAVORITO MANTIDO
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
                print("   -> IA diz: Nada encontrado neste texto.")
        else:
            print("   -> Erro: Site retornou vazio.")
        time.sleep(1)

    if not relatorio_html:
        relatorio_html = "<p style='text-align:center; color:#777;'>Nenhum edital encontrado (Verifique os logs de leitura).</p>"

    html_final = f"""
    <html><body style='font-family:Arial, sans-serif; padding:20px;'>
        <div style='max-width:600px; margin:0 auto; border:1px solid #ddd; padding:20px;'>
            <h2 style='color:#009586; text-align:center;'>SENTINELA GERAL</h2>
            <p style='text-align:center; color:#aaa; font-size:12px;'>Monitoramento sem Filtros</p>
            <hr style='border:0; border-top:1px solid #eee; margin:20px 0;'>
            {relatorio_html}
        </div>
    </body></html>
    """

    print(f">>> Enviando para {len(DESTINOS)} pessoas.")
    msg = EmailMessage()
    msg['Subject'] = f'Sentinela: {total} Oportunidades Gerais'
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL, SENHA)
        s.send_message(msg)
    print("✅ Feito.")
