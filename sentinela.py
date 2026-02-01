import os, smtplib, json, requests, time, urllib3
import google.generativeai as genai
import gspread
from email.message import EmailMessage
from bs4 import BeautifulSoup

# --- 0. CONFIGURAÇÕES AVANÇADAS ---
# Desabilita o aviso chato de segurança
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
            try:
                sh = gc.open("Sentinela Emails")
            except:
                sh = gc.open("Formulário sem título (respostas)")
            vals = sh.sheet1.col_values(3)
            validos = [e.strip() for e in vals if '@' in e and '.' in e and 'email' not in e.lower()]
            if validos: 
                lista = validos
                print(f">>> Sucesso: {len(lista)} destinatários carregados da planilha.")
            else:
                print(">>> Aviso: Planilha lida, mas vazia. Usando e-mail do dono.")
        except Exception as e:
            print(f">>> Erro Planilha: {str(e)[:50]}")
    return lista

DESTINOS = obter_destinatarios()

# --- 2. FONTES OFICIAIS ATUALIZADAS (COM FINEP E PROADI) ---
FONTES = [
    {
        "nome": "FAPERGS (Editais)",
        "url": "https://fapergs.rs.gov.br/editais-abertos",
    },
    {
        "nome": "CNPq (Chamadas Abertas)",
        "url": "https://www.gov.br/cnpq/pt-br/composicao/diretorias/dco/chamadas-publicas/chamadas-publicas-abertas",
    },
    {
        "nome": "FINEP (Inovação)",
        "url": "http://www.finep.gov.br/chamadas-publicas/chamadas-publicas-abertas",
    },
    {
        "nome": "Proadi-SUS (Hospitais)",
        "url": "https://hospitais.proadi-sus.org.br/projetos",
    }
]

def ler_pagina(url):
    """Acessa a página fingindo ser um navegador comum e ignorando SSL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=25, verify=False)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:30000] # Limite aumentado
        else:
            print(f"   -> Erro HTTP {response.status_code}")
    except Exception as e:
        print(f"   -> Erro de Conexão: {str(e)[:100]}...")
    return ""

def analisar_com_gemini(texto_site, nome_fonte):
    if not texto_site: return []
    
    # PROMPT TURBINADO (EDITOR SÊNIOR)
    prompt = f"""
    Atue como Editor Sênior do HCPA. Analise este texto do site: {nome_fonte}.
    
    OBJETIVO:
    Identifique TODAS as chamadas, editais ou oportunidades ABERTAS (2025/2026).
    
    FOCO ESTRATÉGICO:
    1. Física Médica, Radioterapia, Medicina Nuclear.
    2. Inteligência Artificial em Saúde e Inovação Hospitalar.
    3. Compra de Equipamentos ou Bolsas de Pesquisa.
    
    SAÍDA JSON OBRIGATÓRIA:
    [
      {{
        "titulo": "Nome exato da chamada", 
        "resumo": "Resumo focado no benefício (bolsa/equipamento)", 
        "status": "Prazo ou Status" 
      }}
    ]
    
    TEXTO:
    {texto_site}
    """
    
    try:
        resp = MODELO.generate_content(prompt)
        texto_limpo = resp.text.replace('```json', '').replace('```', '')
        return json.loads(texto_limpo)
    except:
        return []

# --- 3. EXECUÇÃO ---
if __name__ == "__main__":
    relatorio_html = ""
    itens_encontrados = 0
    
    print(">>> Iniciando Varredura Modo Furtivo (SSL Ignorado)...")
    
    for fonte in FONTES:
        print(f"... Acessando: {fonte['nome']}")
        conteudo = ler_pagina(fonte['url'])
        
        if conteudo:
            print(f"   -> Leitura OK ({len(conteudo)} caracteres). Enviando para IA...")
            oportunidades = analisar_com_gemini(conteudo, fonte['nome'])
            
            if oportunidades:
                print(f"   -> {len(oportunidades)} itens identificados!")
                itens_encontrados += len(oportunidades)
                
                # --- SEU DESIGN PREFERIDO (Mantido Intacto) ---
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
                print("   -> IA não encontrou editais relevantes no texto.")
        
        time.sleep(1)

    # --- ENVIO ---
    if not relatorio_html:
        relatorio_html = "<p style='text-align:center; color:#777;'>Varredura realizada. Nenhum edital novo detectado hoje.</p>"

    html_final = f"""
    <html><body style='font-family:Arial, sans-serif; padding:20px;'>
        <div style='max-width:600px; margin:0 auto; border:1px solid #ddd; padding:20px;'>
            <h2 style='color:#009586; text-align:center;'>SENTINELA OFICIAL</h2>
            <p style='text-align:center; color:#aaa; font-size:12px;'>Monitoramento Direto (CNPq, FAPERGS, FINEP, Proadi)</p>
            <hr style='border:0; border-top:1px solid #eee; margin:20px 0;'>
            {relatorio_html}
        </div>
    </body></html>
    """

    print(f">>> Enviando relatório para {len(DESTINOS)} pessoas.")
    msg = EmailMessage()
    msg['Subject'] = f'Sentinela: {itens_encontrados} Oportunidades Encontradas'
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
    print("✅ Processo Finalizado.")
