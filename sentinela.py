import os
import smtplib
import time
import requests
import google.generativeai as genai
from email.message import EmailMessage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
# CORREÇÃO AQUI: Voltamos para o import clássico que é compatível com o GitHub Actions atual
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

# --- LISTA DE SITES FIXOS ---
# Adicione aqui os links que você quer monitorar sempre
SITES_FIXOS = [
    ("DOU (Pesquisa)", "https://www.in.gov.br/leiturajornal"),
]

# --- EIXOS TEMÁTICOS (BUSCA ATIVA) ---
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
    "HealthTech", "CNPq", "FAPERGS", "Ministério da Saúde"
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

def analisar_conteudo_site_ia(nome_site, texto_site):
    """
    Manda o conteúdo do site fixo para a IA analisar.
    """
    if not model: return None

    # Corta o texto para não estourar o limite da IA
    texto_resumido = texto_site[:3000]

    prompt = f"""
    Você é um assistente de monitoramento. Analise o texto extraído da página inicial do site '{nome_site}'.
    
    Texto extraído:
    {texto_resumido}

    TAREFA:
    Identifique se há menção explícita a NOVOS editais, chamadas públicas ou processos seletivos abertos recentemente.
    
    SAÍDA:
    - Se encontrar algo relevante: Resuma em 1 frase (Ex: "Publicada edição extra com editais de saúde").
    - Se for apenas texto padrão do site ou navegação: Responda "NÃO".
    """
    try:
        response = model.generate_content(prompt)
        texto_ia = response.text.strip()
        if "NÃO" in texto_ia.upper() or len(texto_ia) < 5:
            return None
        return texto_ia
    except:
        return None

def analisar_site_fixo(nome, url, session):
    """
    Acessa o site, verifica status e usa IA para ler o conteúdo.
    Retorna tupla: (Icone, Nome, Url, Resumo_IA, Cor)
    """
    try:
        resp = session.get(url, timeout=20)
        
        if resp.status_code != 200:
            return ("⚠️", nome, url, f"Erro ao acessar: Status {resp.status_code}", "orange")

        soup = BeautifulSoup(resp.content, 'html.parser')
        texto = soup.get_text().strip()
        
        # 1. Verifica palavras-chave básicas primeiro
        termos_interesse = ["edital", "chamada", "inscriç", "publicado", "aviso"]
        if any(x in texto.lower() for x in termos_interesse):
            
            # 2. Se achou palavras, chama a IA para ler o que é
            analise_ia = analisar_conteudo_site_ia(nome, texto)
            
            if analise_ia:
                return ("✅", nome, url, analise_ia, "green")
            else:
                return ("ℹ️", nome, url, "Site acessível (IA não detectou novidades urgentes)", "#555")
        
        return ("ℹ️", nome, url, "Site acessível.", "#555")

    except Exception as e:
        return ("❌", nome, url, "Falha de conexão.", "red")

def consultar_ia_busca(titulo, snippet, tema):
    """Filtro IA para os resultados da Busca Web"""
    if not model: return None 
    prompt = f"""
    Analise este resultado de busca sobre '{tema}':
    Título: {titulo} | Resumo: {snippet}
    Responda APENAS:
    - "NÃO" se for irrelevante, antigo, venda ou rede social.
    - Um resumo de 1 linha se for oportunidade real (Edital/Bolsa/Grant 2025-2026).
    """
    try:
        response = model.generate_content(prompt)
        t = response.text.strip()
        return None if "NÃO" in t.upper() or len(t) < 5 else t
    except: return None

def realizar_busca(temas, query_pattern, label_log):
    html_items = ""
    # Instancia DDGS com timeout seguro
    with DDGS(timeout=25) as ddgs:
        for tema in temas:
            termo = query_pattern.format(tema)
            try:
                time.sleep(2) # Pausa anti-bloqueio
                results = list(ddgs.text(termo, max_results=2))
                if results:
                    for r in results:
                        titulo = r.get('title', 'Sem título')
                        link = r.get('href', '')
                        snippet = r.get('body', '')
                        analise = consultar_ia_busca(titulo, snippet, tema)
                        if analise:
                            tag_pdf = " 📄 <strong>[PDF]</strong>" if link.lower().endswith('.pdf') else ""
                            html_items += f"""
                                <li style="margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px dashed #eee;">
                                    <a href="{link}" style="font-size: 14px; color: #007bff; text-decoration: none; font-weight: 600;">{titulo}</a>{tag_pdf}
                                    <div style="font-size: 12px; color: #444; margin-top: 3px;">🤖 {analise}</div>
                                </li>"""
            except: continue
    return html_items

def buscar_por_eixo(nome_eixo, lista_temas, cor_titulo):
    print(f"--- Eixo: {nome_eixo} ---")
    # Busca Brasil e Mundo
    html_br = realizar_busca(lista_temas, '"{}" (edital OR chamada OR processo seletivo) 2025..2026 site:.br', "BR")
    html_world = realizar_busca(lista_temas, '"{}" (grant OR funding OR phd position) 2025..2026 -site:.br', "WORLD")
    
    if not html_br and not html_world: return ""
    
    conteudo = f"""<div style="margin-bottom: 20px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: {cor_titulo}; color: white; padding: 10px; font-weight: bold;">{nome_eixo}</div>
        <div style="padding: 15px; background: #fff;">"""
        
    if html_br: conteudo += f"<div style='margin-bottom:10px;'><div style='font-size:11px;font-weight:bold;color:#666;border-bottom:1px solid #eee;'>🇧🇷 BRASIL</div><ul style='padding-left:0;list-style:none;'>{html_br}</ul></div>"
    if html_world: conteudo += f"<div><div style='font-size:11px;font-weight:bold;color:#666;border-bottom:1px solid #eee;'>🌍 MUNDO</div><ul style='padding-left:0;list-style:none;'>{html_world}</ul></div>"
    
    return conteudo + "</div></div>"

def executar_sentinela():
    session = criar_sessao_robusta()
    
    # 1. PROCESSAR SITES FIXOS
    html_fixos = ""
    for nome, url in SITES_FIXOS:
        res = analisar_site_fixo(nome, url, session)
        html_fixos += f"""
        <div style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee;">
            <div style="font-size: 14px;">
                {res[0]} <a href="{res[2]}" style="text-decoration: none; color: #2c3e50; font-weight: bold;">{res[1]}</a>
            </div>
            <div style="font-size: 12px; color: {res[4]}; margin-top: 4px; margin-left: 24px;">
                {res[3]}
            </div>
        </div>
        """

    # 2. PROCESSAR BUSCA
    html_busca = ""
    html_busca += buscar_por_eixo("☢️ Nuclear & Física Médica", EIXO_NUCLEAR, "#8e44ad")
    html_busca += buscar_por_eixo("💻 Inteligência Artificial", EIXO_IA_SAUDE, "#2980b9")
    html_busca += buscar_por_eixo("🏥 Gestão & Fomento", EIXO_GESTAO, "#27ae60")

    if not html_busca:
        html_busca = "<p style='text-align:center;color:#999;'>Nenhuma oportunidade nova encontrada na busca ativa.</p>"

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Segoe UI', sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 650px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); overflow: hidden;">
            <div style="background-color: #2c3e50; padding: 20px; text-align: center; color: white;">
                <h2 style="margin:0;">SENTINELA</h2>
                <p style="margin:5px 0 0; font-size:12px; color:#bdc3c7;">Monitoramento Integrado</p>
            </div>
            <div style="padding: 20px;">
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 25px;">
                    <h3 style="margin-top:0; font-size:14px; color:#6c757d; text-transform:uppercase;">📍 Monitoramento Fixo</h3>
                    {html_fixos}
                </div>
                
                <h3 style="font-size:14px; color:#6c757d; text-transform:uppercase; margin-bottom: 15px;">🚀 Radar de Oportunidades</h3>
                {html_busca}
            </div>
            <div style="text-align:center; padding:10px; background:#eee; font-size:10px; color:#777;">
                Gerado automaticamente via GitHub Actions
            </div>
        </div>
    </body>
    </html>
    """

def enviar_email(html_content):
    if not EMAIL_ORIGEM or not SENHA_APP: return
    msg = EmailMessage()
    msg['Subject'] = 'Sentinela: Relatório Diário'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = EMAIL_DESTINO
    msg.add_alternative(html_content, subtype='html')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ORIGEM, SENHA_APP)
        smtp.send_message(msg)

if __name__ == "__main__":
    enviar_email(executar_sentinela())
