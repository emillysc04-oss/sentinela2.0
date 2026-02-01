import os, smtplib, json, time, requests, urllib3, urllib.parse
import google.generativeai as genai
import gspread
import xml.etree.ElementTree as ET
from email.message import EmailMessage

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

# --- 2. FONTES (AGORA USANDO GOOGLE NEWS RSS) ---
# Em vez de links diretos que quebram, usamos buscas no Google News restritas ao site oficial
FONTES = [
    {
        "nome": "FAPERGS (Via Google News)",
        # Busca: site:fapergs.rs.gov.br e (Edital OU Chamada) nos ultimos 90 dias
        "query": "site:fapergs.rs.gov.br (Edital OR Chamada) when:90d"
    },
    {
        "nome": "CNPq (Via Google News)",
        "query": "site:gov.br/cnpq (Chamada OR Bolsa OR Edital) when:30d"
    },
    {
        "nome": "FINEP (Via Google News)",
        "query": "site:finep.gov.br (Chamada OR Seleção) when:60d"
    },
    {
        "nome": "Proadi-SUS (Via Google News)",
        "query": "site:proadi-sus.org.br (Edital OR Seleção OR Projeto) when:90d"
    }
]

def buscar_rss(query):
    """Busca no Google News RSS - Imune a bloqueios de IP"""
    base_url = "https://news.google.com/rss/search"
    params = {
        "q": query,
        "hl": "pt-BR",
        "gl": "BR",
        "ceid": "BR:pt-419"
    }
    
    try:
        # User-Agent simples funciona bem com RSS do Google
        response = requests.get(base_url, params=params, timeout=20)
        
        if response.status_code == 200:
            # Parseia o XML do RSS
            root = ET.fromstring(response.content)
            texto_agregado = ""
            
            # Pega as top 10 notícias do feed
            for item in root.findall('.//item')[:10]:
                titulo = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                data = item.find('pubDate').text if item.find('pubDate') is not None else ""
                
                texto_agregado += f"TITULO: {titulo}\nLINK: {link}\nDATA: {data}\n---\n"
            
            return texto_agregado
        else:
            print(f"   -> Erro RSS Google: {response.status_code}")
    except Exception as e:
        print(f"   -> Erro Conexão RSS: {str(e)[:100]}")
    return ""

def analisar_com_gemini(texto_rss, nome_fonte):
    if not texto_rss: return []
    
    prompt = f"""
    Analise esta lista de notícias recentes do {nome_fonte}.
    
    MISSÃO:
    Identifique editais, chamadas ou oportunidades de fomento para pesquisadores da saúde (Física Médica, IA, Radioterapia).
    
    CRITÉRIOS:
    - Ignore notícias administrativas (ex: "Diretor viaja", "Reunião").
    - Fioque em: LANÇAMENTO DE EDITAL, CHAMADA ABERTA, INSCRIÇÕES.
    
    SAÍDA JSON:
    [ {{ "titulo": "Titulo da Notícia", "resumo": "Explique a oportunidade", "status": "Link ou Data mencionada" }} ]
    
    DADOS DO RSS:
    {texto_rss}
    """
    try:
        resp = MODELO.generate_content(prompt)
        return json.loads(resp.text.replace('```json', '').replace('```', ''))
    except: return []

# --- 3. EXECUÇÃO ---
if __name__ == "__main__":
    relatorio_html = ""
    total = 0
    print(">>> Iniciando Sentinela 57.0 (Estratégia Google RSS)...")
    
    for fonte in FONTES:
        print(f"... Consultando Google News: {fonte['nome']}")
        conteudo = buscar_rss(fonte['query'])
        
        if conteudo:
            print(f"   -> Feed recebido! IA Analisando...")
            oportunidades = analisar_com_gemini(conteudo, fonte['nome'])
            
            if oportunidades:
                print(f"   -> {len(oportunidades)} itens encontrados.")
                total += len(oportunidades)
                # SEU DESIGN FAVORITO (MANTIDO)
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
                print("   -> IA analisou o feed, mas não viu editais novos de Saúde/Física.")
        else:
            print("   -> Feed vazio ou erro.")
        time.sleep(1)

    if not relatorio_html:
        relatorio_html = "<p style='text-align:center; color:#777;'>Nenhuma novidade encontrada nos feeds hoje.</p>"

    html_final = f"""
    <html><body style='font-family:Arial, sans-serif; padding:20px;'>
        <div style='max-width:600px; margin:0 auto; border:1px solid #ddd; padding:20px;'>
            <h2 style='color:#009586; text-align:center;'>SENTINELA RSS</h2>
            <p style='text-align:center; color:#aaa; font-size:12px;'>Monitoramento via Google News</p>
            <hr style='border:0; border-top:1px solid #eee; margin:20px 0;'>
            {relatorio_html}
        </div>
    </body></html>
    """

    print(f">>> Enviando para {len(DESTINOS)} pessoas.")
    msg = EmailMessage()
    msg['Subject'] = f'Sentinela: {total} Oportunidades (RSS Feed)'
    msg['From'] = EMAIL
    msg['To'] = EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
        s.login(EMAIL, SENHA)
        s.send_message(msg)
    print("✅ Sucesso!")
