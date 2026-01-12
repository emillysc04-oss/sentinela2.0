import os
import smtplib
import time
import requests
import google.generativeai as genai
from email.message import EmailMessage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

# --- CONFIGURAÇÕES E CREDENCIAIS ---
EMAIL_ORIGEM = os.environ.get('EMAIL_REMETENTE')
SENHA_APP = os.environ.get('SENHA_APP')
EMAIL_DESTINO = EMAIL_ORIGEM
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

# Configuração da IA (Gemini)
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash') # Modelo rápido e barato/grátis
else:
    model = None
    print("AVISO: GEMINI_API_KEY não encontrada. A IA não será usada.")

# --- EIXOS TEMÁTICOS ---
EIXO_NUCLEAR = [
    "Radioterapia", "Radiofármacos", "Medicina Nuclear", "Dosimetria", 
    "Braquiterapia", "Acelerador Linear", "Proteção Radiológica"
]

EIXO_IA_SAUDE = [
    "Inteligência Artificial saúde", "Machine Learning médica", 
    "Deep Learning medicina", "Radiômica", "Saúde 4.0", "Big Data em Saúde"
]

EIXO_GESTAO = [
    "Avaliação de Tecnologias em Saúde", "Inovação Hospitalar", 
    "Pesquisa Clínica", "Proadi-SUS", "HealthTech", "Soberania Sanitária"
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
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return ("⚠️", f"{nome}: Erro {resp.status_code}", "orange")
        soup = BeautifulSoup(resp.content, 'html.parser')
        texto = soup.get_text().lower()
        if any(x in texto for x in ["edital", "chamada", "inscrições abertas"]):
            return ("✅", f"{nome}: Possível edital aberto detectado.", "green")
        return ("ℹ️", f"{nome}: Sem termos de abertura hoje.", "#777")
    except:
        return ("❌", f"{nome}: Falha de conexão.", "red")

def consultar_ia(titulo, snippet, tema):
    """
    Usa a IA para decidir se o link vale a pena.
    Retorna: O resumo feito pela IA ou None se for irrelevante.
    """
    if not model:
        return f"Resultado automático (Sem IA): {titulo}"

    prompt = f"""
    Analise este resultado de busca sobre '{tema}':
    Título: {titulo}
    Resumo: {snippet}

    Tarefa:
    1. Isso parece ser uma oportunidade REAL de financiamento, edital, bolsa ou evento acadêmico futuro (2025/2026)?
    2. Se for apenas um artigo científico antigo, notícia velha ou irrelevante, responda apenas "NÃO".
    3. Se for relevante, responda com uma frase curta resumindo a oportunidade e o prazo de submissão.

    Responda em Português.
    """
    
    try:
        response = model.generate_content(prompt)
        texto_ia = response.text.strip()
        
        if "NÃO" in texto_ia.upper() and len(texto_ia) < 10:
            return None # IA decidiu que é lixo
        
        return texto_ia # Retorna o resumo da IA
    except Exception as e:
        print(f"Erro na IA: {e}")
        return titulo # Se a IA falhar, devolve o título original

def buscar_por_eixo(nome_eixo, lista_temas, cor_titulo):
    itens_html = ""
    encontrou_algo = False
    print(f"--- Processando: {nome_eixo} ---")

    with DDGS() as ddgs:
        for tema in lista_temas:
            # Busca mais ampla, deixa a IA filtrar
            termo = f'"{tema}" (edital OR chamada OR grant OR bolsa) 2026'
            try:
                # Pausa para respeitar limites (Rate Limits da IA e do Buscador)
                time.sleep(4) 
                
                results = list(ddgs.text(termo, max_results=2))
                
                if results:
                    for r in results:
                        titulo = r.get('title', '')
                        link = r.get('href', '')
                        snippet = r.get('body', '') # O resumo que o buscador dá
                        
                        # --- AQUI ENTRA A IA ---
                        analise = consultar_ia(titulo, snippet, tema)
                        
                        if analise: # Só adiciona se a IA aprovou
                            encontrou_algo = True
                            print(f"  [IA Aprovou]: {titulo[:30]}...")
                            
                            tag_pdf = ""
                            if link.lower().endswith('.pdf'):
                                tag_pdf = " <span style='background:#d9534f;color:white;padding:2px 4px;border-radius:3px;font-size:10px;'>PDF</span>"

                            itens_html += f"""
                                <li style="margin-bottom: 12px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                                    <div style="font-weight:bold; color:#444;">{tema}:</div>
                                    <a href="{link}" style="color:#007bff; text-decoration:none; font-weight:bold;">{titulo}</a>{tag_pdf}
                                    <div style="font-size:13px; color:#555; margin-top:2px;">🤖 <em>{analise}</em></div>
                                </li>
                            """
                        else:
                            print(f"  [IA Rejeitou]: {titulo[:30]}...")

            except Exception as e:
                print(f"Erro busca '{tema}': {e}")
                continue

    if not encontrou_algo:
        return ""

    return f"""
    <div style="margin-bottom: 20px; border: 1px solid {cor_titulo}; border-radius: 8px; overflow: hidden;">
        <div style="background-color: {cor_titulo}; color: white; padding: 10px; font-weight: bold;">
            {nome_eixo}
        </div>
        <div style="padding: 15px; background-color: #fff;">
            <ul style="padding-left: 0; list-style: none; margin: 0;">
                {itens_html}
            </ul>
        </div>
    </div>
    """

def executar_sentinela():
    session = criar_sessao_robusta()
    
    # Sites Fixos
    fapergs = analisar_site_fixo("FAPERGS", "https://fapergs.rs.gov.br/editais-abertos", session)
    dou = analisar_site_fixo("DOU", "https://www.in.gov.br/leiturajornal", session)
    
    # Busca IA
    html_nuclear = buscar_por_eixo("☢️ Nuclear & Radioproteção", EIXO_NUCLEAR, "#6f42c1")
    html_ia = buscar_por_eixo("💻 IA & Saúde Digital", EIXO_IA_SAUDE, "#0d6efd")
    html_gestao = buscar_por_eixo("🏥 Gestão & Inovação", EIXO_GESTAO, "#198754")

    conteudo_busca = html_nuclear + html_ia + html_gestao
    if not conteudo_busca:
        conteudo_busca = "<p style='text-align:center; color:#666;'>A IA analisou os resultados e não encontrou oportunidades de alta relevância hoje.</p>"

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <h2 style="color: #333; border-bottom: 2px solid #0d6efd; padding-bottom: 10px;">Sentinela Inteligente 🤖</h2>
            
            <div style="background: #eef; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                <strong>Status Portais:</strong><br>
                {fapergs[0]} <a href="https://fapergs.rs.gov.br/editais-abertos" style="color:#333; text-decoration:none;">{fapergs[1]}</a><br>
                {dou[0]} <a href="https://www.in.gov.br/leiturajornal" style="color:#333; text-decoration:none;">{dou[1]}</a>
            </div>

            <h3 style="color: #555;">Análise de Oportunidades (Via AI)</h3>
            {conteudo_busca}
            
            <p style="text-align: center; font-size: 11px; color: #aaa; margin-top: 30px;">
                Gerado por Sentinela v6.0 usando Google Gemini Flash
            </p>
        </div>
    </body>
    </html>
    """

def enviar_email(html_content):
    if not EMAIL_ORIGEM or not SENHA_APP: return
    msg = EmailMessage()
    msg['Subject'] = 'Sentinela: Relatório diário'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = EMAIL_DESTINO
    msg.add_alternative(html_content, subtype='html')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ORIGEM, SENHA_APP)
        smtp.send_message(msg)

if __name__ == "__main__":
    enviar_email(executar_sentinela())
