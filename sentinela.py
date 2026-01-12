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

# --- CONFIGURAÇÕES ---
EMAIL_ORIGEM = os.environ.get('EMAIL_REMETENTE')
SENHA_APP = os.environ.get('SENHA_APP')
EMAIL_DESTINO = EMAIL_ORIGEM
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

# Configuração da IA
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

# --- EIXOS TEMÁTICOS ---
EIXO_NUCLEAR = [
    "Radioterapia", "Radiofármacos", "Medicina Nuclear", "Física Médica",
    "Dosimetria", "Proteção Radiológica"
]

EIXO_IA_SAUDE = [
    "Inteligência Artificial saúde", "Machine Learning médica", 
    "Deep Learning medicina", "Saúde Digital", "Big Data em Saúde"
]

EIXO_GESTAO = [
    "Avaliação de Tecnologias em Saúde", "Inovação Hospitalar", 
    "Pesquisa Clínica", "Proadi-SUS", "HealthTech", 
    "CNPq", "FAPERGS", "Ministério da Saúde"
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
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return (f"{nome}: Erro {resp.status_code}", "orange")
        soup = BeautifulSoup(resp.content, 'html.parser')
        texto = soup.get_text().lower()
        if any(x in texto for x in ["edital", "chamada", "inscrições abertas", "publicado"]):
            return ("✅", f"{nome}: Termos de edital detectados na página.", "green")
        return ("ℹ️", f"{nome}: Página acessível, sem novidades óbvias.", "#777")
    except:
        return ("❌", f"{nome}: Falha de conexão.", "red")

def consultar_ia(titulo, snippet, tema):
    """
    O Filtro Supremo. Se não for bom, retorna None.
    """
    if not model: return None 

    prompt = f"""
    Analise este resultado de busca para o tema '{tema}':
    Título: {titulo}
    Resumo: {snippet}

    Critérios de Aprovação:
    1. DEVE ser uma oportunidade: Edital, Bolsa, Grant, Financiamento, Vaga de Doutorado/Pesquisa ou Chamada de Trabalhos.
    2. DEVE ser atual (vigente para 2025 ou 2026).
    3. NÃO pode ser venda de produtos, curso pago genérico, notícia velha, artigo de opinião ou rede social.

    Responda:
    - Se for irrelevante: Responda apenas "NÃO".
    - Se for relevante: Responda com uma frase resumindo a oportunidade (Ex: "Grant de €50k para IA na Europa").
    """
    
    try:
        response = model.generate_content(prompt)
        texto_ia = response.text.strip()
        
        if "NÃO" in texto_ia.upper() or len(texto_ia) < 5:
            return None
        
        return texto_ia
    except:
        return None

def realizar_busca(temas, query_suffix, gatilhos, label_log):
    """
    Função genérica para buscar (Brasil ou Mundo).
    Retorna uma string HTML com os itens <li>.
    """
    html_items = ""
    with DDGS(timeout=25) as ddgs:
        for tema in temas:
            # Monta a query: "Tema" (gatilho1 OR gatilho2) 2025..2026 sufixo
            termo = f'"{tema}" ({gatilhos}) 2025..2026 {query_suffix}'
            
            try:
                time.sleep(3) # Pausa para não ser bloqueado
                results = list(ddgs.text(termo, max_results=2))
                
                if results:
                    for r in results:
                        titulo = r.get('title', 'Sem título')
                        link = r.get('href', '')
                        snippet = r.get('body', '')

                        # Filtro IA
                        analise = consultar_ia(titulo, snippet, tema)
                        
                        if analise:
                            print(f"  [{label_log} Aprovado]: {titulo[:40]}...")
                            
                            tag_pdf = ""
                            if link.lower().endswith('.pdf'):
                                tag_pdf = " 📄 <strong>[PDF]</strong>"

                            html_items += f"""
                                <li style="margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px dashed #eee;">
                                    <a href="{link}" style="font-size: 14px; color: #007bff; text-decoration: none; font-weight: 600;">
                                        {titulo}
                                    </a>{tag_pdf}
                                    <div style="font-size: 12px; color: #444; margin-top: 3px;">
                                        🤖 {analise}
                                    </div>
                                </li>
                            """
            except Exception as e:
                print(f"Erro em {label_log} / {tema}: {e}")
                continue
    return html_items

def buscar_por_eixo(nome_eixo, lista_temas, cor_titulo):
    print(f"--- Iniciando Eixo: {nome_eixo} ---")
    
    # 1. Busca BRASIL
    # Gatilhos em PT, restrito ao domínio .br
    html_br = realizar_busca(
        lista_temas, 
        "site:.br", 
        "edital OR chamada pública OR bolsa pesquisa OR processo seletivo", 
        "BR"
    )

    # 2. Busca INTERNACIONAL
    # Gatilhos em EN, EXCLUINDO domínio .br (-site:.br)
    html_world = realizar_busca(
        lista_temas, 
        "-site:.br", 
        "grant OR research funding OR phd position OR call for papers", 
        "WORLD"
    )

    # Se não achou nada em lugar nenhum, não retorna o bloco do eixo
    if not html_br and not html_world:
        return ""

    # Monta o HTML do Eixo
    conteudo_eixo = f"""
    <div style="margin-bottom: 25px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; font-family: sans-serif;">
        <div style="background-color: {cor_titulo}; color: white; padding: 10px 15px; font-weight: bold;">
            {nome_eixo}
        </div>
        <div style="padding: 15px; background-color: #fff;">
    """

    if html_br:
        conteudo_eixo += f"""
            <div style="margin-bottom: 15px;">
                <div style="font-size: 11px; font-weight: bold; color: #666; text-transform: uppercase; border-bottom: 2px solid #eee; margin-bottom: 8px;">
                    Brasil
                </div>
                <ul style="padding-left: 0; list-style: none; margin: 0;">{html_br}</ul>
            </div>
        """
    
    if html_world:
        conteudo_eixo += f"""
            <div>
                <div style="font-size: 11px; font-weight: bold; color: #666; text-transform: uppercase; border-bottom: 2px solid #eee; margin-bottom: 8px;">
                    Internacional
                </div>
                <ul style="padding-left: 0; list-style: none; margin: 0;">{html_world}</ul>
            </div>
        """

    conteudo_eixo += "</div></div>"
    return conteudo_eixo

def executar_sentinela():
    session = criar_sessao_robusta()
    
    # Status Fixo (DOU)
    dou = analisar_site_fixo("DOU (Pesquisa)", "https://www.in.gov.br/leiturajornal", session)
    
    # Busca Inteligente por Eixos
    html_nuclear = buscar_por_eixo("☢️ Nuclear & Física Médica", EIXO_NUCLEAR, "#8e44ad") # Roxo
    html_ia = buscar_por_eixo("💻 Inteligência Artificial", EIXO_IA_SAUDE, "#2980b9") # Azul
    html_gestao = buscar_por_eixo("🏥 Gestão & Fomento", EIXO_GESTAO, "#27ae60") # Verde

    conteudo_principal = html_nuclear + html_ia + html_gestao
    
    if not conteudo_principal:
        conteudo_principal = """
        <div style="text-align: center; padding: 40px; color: #999; background: #f9f9f9; border-radius: 8px;">
            <p><strong>Nenhuma oportunidade relevante detectada hoje.</strong></p>
            <p style="font-size: 12px;">Os filtros de IA analisaram as buscas e descartaram resultados irrelevantes.</p>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4; padding: 20px; margin: 0;">
        <div style="max-width: 650px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); overflow: hidden;">
            
            <div style="background-color: #34495e; padding: 20px; text-align: center;">
                <h2 style="color: #fff; margin: 0; font-size: 22px;">SENTINELA</h2>
                <p style="color: #bdc3c7; margin: 5px 0 0 0; font-size: 12px;">Radar Diário de Oportunidades</p>
            </div>

            <div style="padding: 25px;">
                <div style="margin-bottom: 25px; padding: 10px; background: #ecf0f1; border-radius: 6px; font-size: 13px;">
                    {dou[0]} <a href="https://www.in.gov.br/leiturajornal" style="color: #2c3e50; text-decoration: none; font-weight: bold;">{dou[1]}</a>
                </div>

                {conteudo_principal}
            </div>
            
            <div style="background-color: #eee; padding: 10px; text-align: center; font-size: 10px; color: #888;">
                Filtro IA Ativo • Powered by Gemini Flash
            </div>
        </div>
    </body>
    </html>
    """

def enviar_email(html_content):
    if not EMAIL_ORIGEM or not SENHA_APP: return
    msg = EmailMessage()
    msg['Subject'] = 'Sentinela: Radar de Oportunidades'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = EMAIL_DESTINO
    msg.add_alternative(html_content, subtype='html')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ORIGEM, SENHA_APP)
        smtp.send_message(msg)

if __name__ == "__main__":
    enviar_email(executar_sentinela())
