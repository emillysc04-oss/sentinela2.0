import os, smtplib, json, requests, time
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
            sh = gc.open_by_key("SEU_ID_PLANILHA") if "http" in str(SHEETS_JSON) else None 
            # Método de fallback seguro para abrir planilha pelo nome
            try:
                sh = gc.open("Sentinela Emails")
            except:
                sh = gc.open("Formulário sem título (respostas)")
            
            vals = sh.sheet1.col_values(3)
            validos = [e.strip() for e in vals if '@' in e and '.' in e and 'email' not in e.lower()]
            if validos: lista = validos
            print(f">>> Destinatários: {len(lista)}")
        except: pass
    return lista

DESTINOS = obter_destinatarios()

# --- 2. FONTES OFICIAIS (A MÁGICA) ---
# Aqui listamos as páginas EXATAS onde os editais são publicados
FONTES = [
    {
        "nome": "FAPERGS (Editais Abertos)",
        "url": "https://fapergs.rs.gov.br/editais-abertos",
        "seletor": "body" # Lê o corpo todo
    },
    {
        "nome": "CNPq (Chamadas Públicas)",
        "url": "http://memoria.cnpq.br/web/guest/chamadas-publicas",
        "seletor": ".journal-content-article"
    },
    {
        "nome": "Ministério da Saúde (Seleções)",
        "url": "https://www.gov.br/saude/pt-br/composicao/sectics/deciis/editais-de-projetos",
        "seletor": "body"
    }
]

def ler_pagina(url):
    """Acessa a página como um navegador comum"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Garante que acentos fiquem corretos
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Remove scripts e estilos para limpar o texto
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()
            text = soup.get_text(separator=' ', strip=True)
            # Limita o tamanho para não estourar o Gemini (20k caracteres)
            return text[:20000] 
    except Exception as e:
        print(f"Erro ao ler {url}: {e}")
    return ""

def analisar_com_gemini(texto_site, nome_fonte):
    """Envia o texto cru do site para o Gemini garimpar"""
    if not texto_site: return []
    
    prompt = f"""
    Você é um Especialista em Fomento à Pesquisa do HCPA.
    Abaixo está o CONTEÚDO DE TEXTO extraído diretamente do site oficial: {nome_fonte}.
    
    SUA MISSÃO:
    Analise o texto e encontre TODAS as chamadas, editais ou seleções que estejam ABERTAS ou VIGENTES em 2025/2026.
    
    FILTRO DE TEMA (Seja amplo):
    Saúde, Medicina, Física Médica, Radioterapia, Inteligência Artificial, Inovação, Tecnologia Hospitalar, Bolsas de Pesquisa.
    
    REGRAS:
    1. Retorne APENAS oportunidades reais encontradas no texto.
    2. Se não tiver nada relevante, retorne lista vazia.
    3. Formato JSON: [{{ "titulo": "Nome do Edital", "resumo": "Explicação breve", "prazo": "Data limite se houver" }}]
    
    TEXTO DO SITE:
    {texto_site}
    """
    
    try:
        resp = MODELO.generate_content(prompt)
        return json.loads(resp.text)
    except:
        return []

# --- 3. EXECUÇÃO ---
if __name__ == "__main__":
    relatorio_geral = ""
    total_encontrado = 0
    
    print(">>> Iniciando Varredura de Fontes Oficiais...")
    
    for fonte in FONTES:
        print(f"... Lendo: {fonte['nome']}")
        conteudo = ler_pagina(fonte['url'])
        
        if conteudo:
            print(f"   -> Conteúdo extraído ({len(conteudo)} caracteres). Analisando...")
            oportunidades = analisar_com_gemini(conteudo, fonte['nome'])
            
            if oportunidades:
                total_encontrado += len(oportunidades)
                relatorio_geral += f"<div style='margin-bottom:30px;'><h3 style='color:#009586; border-bottom:2px solid #009586;'>Fonte: {fonte['nome']}</h3><ul>"
                for item in oportunidades:
                    relatorio_geral += f"""
                    <li style='margin-bottom:15px;'>
                        <strong style='font-size:16px; color:#333;'>{item.get('titulo')}</strong><br>
                        <span style='color:#555; font-size:14px;'>{item.get('resumo')}</span><br>
                        <span style='font-size:12px; font-weight:bold; color:#d32f2f;'>Prazo/Info: {item.get('prazo', 'Verificar edital')}</span>
                    </li>
                    """
                relatorio_geral += "</ul></div>"
        else:
            print("   -> Falha na leitura do site.")
        
        time.sleep(2) # Pausa respeitosa

    # --- ENVIO DO E-MAIL ---
    if not relatorio_geral:
        relatorio_geral = "<p style='text-align:center; padding:30px; color:#777;'>Nenhum edital novo identificado hoje nas páginas oficiais monitoradas.</p>"

    html_final = f"""
    <html><body style='font-family:Segoe UI, Arial, sans-serif; padding:20px; background:#f4f4f4;'>
        <div style='max-width:700px; margin:0 auto; background:#fff; padding:30px; border-top:6px solid #009586; border-radius:4px;'>
            <div style='text-align:center; margin-bottom:30px;'>
                <h2 style='color:#009586; margin:0;'>SENTINELA OFICIAL</h2>
                <p style='color:#666; font-size:14px;'>Monitoramento Direto de Portais (Sem Busca Google)</p>
            </div>
            {relatorio_geral}
            <div style='margin-top:40px; border-top:1px solid #eee; padding-top:20px; text-align:center; font-size:12px; color:#aaa;'>
                Hospital de Clínicas de Porto Alegre • IA Generativa
            </div>
        </div>
    </body></html>
    """

    print(f">>> Enviando relatório com {total_encontrado} oportunidades para {len(DESTINOS)} pessoas.")
    msg = EmailMessage()
    msg['Subject'] = f'Sentinela: {total_encontrado} Novas Oportunidades Detectadas'
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
    print("✅ Sucesso Absoluto!")
