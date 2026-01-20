import os
import time
import smtplib
import requests
import google.generativeai as genai
from email.message import EmailMessage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

# ==============================================================================
# 1. CONFIGURAÇÕES E SEGREDOS (Edite aqui)
# ==============================================================================

# Credenciais (Vêm do GitHub Secrets)
EMAIL_ORIGEM  = os.environ.get('EMAIL_REMETENTE')
SENHA_APP     = os.environ.get('SENHA_APP')
EMAIL_DESTINO = EMAIL_ORIGEM
GEMINI_KEY    = os.environ.get('GEMINI_API_KEY')

# Configuração da IA
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    MODELO_IA = genai.GenerativeModel('gemini-1.5-flash')
else:
    MODELO_IA = None

# Listas de Monitoramento
SITES_FIXOS = [
    # (Nome no Relatório, URL)
    ("DOU (Pesquisa)", "https://www.in.gov.br/leiturajornal"),
]

# Eixos de Busca (Palavras-Chave)
EIXOS = {
    "☢️ Nuclear & Física Médica": {
        "cor": "#8e44ad", # Roxo
        "temas": ["Radioterapia", "Radiofármacos", "Medicina Nuclear", "Física Médica", "Dosimetria", "Proteção Radiológica"]
    },
    "💻 Inteligência Artificial": {
        "cor": "#2980b9", # Azul
        "temas": ["Inteligência Artificial saúde", "Machine Learning médica", "Deep Learning medicina", "Saúde Digital", "Big Data em Saúde"]
    },
    "🏥 Gestão & Fomento": {
        "cor": "#27ae60", # Verde
        "temas": ["Avaliação de Tecnologias em Saúde", "Inovação Hospitalar", "HealthTech", "CNPq", "FAPERGS", "Ministério da Saúde"]
    }
}

# ==============================================================================
# 2. FERRAMENTAS AUXILIARES (O Motor)
# ==============================================================================

def criar_sessao_segura():
    """Cria um navegador falso que insiste se a conexão falhar."""
    session = requests.Session()
    # Tenta 3 vezes se der erro de conexão (500, 502, etc)
    retry = Retry(connect=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    # Identidade do navegador (para não ser bloqueado)
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
    return session

def consultar_gemini(texto_entrada, tipo_analise="busca"):
    """
    O Cérebro. Recebe um texto e decide se é útil ou lixo.
    tipo_analise: 'busca' (para links do Google) ou 'site' (para leitura de página inteira)
    """
    if not MODELO_IA: return None

    # Define o comportamento baseado no tipo de análise
    if tipo_analise == "site":
        contexto = "Analise o texto extraído da página inicial de um site oficial."
    else:
        contexto = "Analise este resultado de busca (Título + Resumo)."

    prompt = f"""
    {contexto}
    Conteúdo para análise:
    {texto_entrada[:3000]} 

    TAREFA:
    Você é um filtro rigoroso para pesquisadores.
    1. Identifique oportunidades REAIS: Editais, Bolsas, Grants, Chamadas Públicas (Vigência 2025/2026).
    2. IGNORE: Notícias velhas, artigos de opinião, vendas, cursos genéricos, redes sociais.
    
    RESPOSTA:
    - Se for irrelevante: Responda apenas "NÃO".
    - Se for relevante: Responda com um resumo de 1 frase (Ex: "Edital aberto para bolsas de doutorado").
    """
    
    try:
        response = MODELO_IA.generate_content(prompt)
        resposta_limpa = response.text.strip()
        
        # Filtro de rejeição
        if "NÃO" in resposta_limpa.upper() or len(resposta_limpa) < 5:
            return None
        return resposta_limpa
    except Exception as e:
        print(f"Erro na IA: {e}")
        return None

# ==============================================================================
# 3. FUNÇÕES DE MONITORAMENTO (Os Operários)
# ==============================================================================

def verificar_site_fixo(nome, url, session):
    """Acessa um link direto e pede pra IA ler a página."""
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return ("⚠️", nome, url, f"Erro: {resp.status_code}", "orange")

        # Extrai texto do HTML
        soup = BeautifulSoup(resp.content, 'html.parser')
        texto_pagina = soup.get_text().strip()

        # Filtro Rápido: Só chama a IA se tiver cheiro de edital
        gatilhos = ["edital", "chamada", "inscriç", "publicado", "aviso"]
        if any(g in texto_pagina.lower() for g in gatilhos):
            resumo = consultar_gemini(texto_pagina, tipo_analise="site")
            if resumo:
                return ("✅", nome, url, resumo, "green")
        
        return ("ℹ️", nome, url, "Acessível, sem novidades urgentes.", "#555")
    except:
        return ("❌", nome, url, "Falha de conexão.", "red")

def _realizar_varredura_ddg(temas, sufixo_busca):
    """Função interna que executa a busca no DuckDuckGo."""
    itens_html = ""
    # Timeout de 25s para evitar travamento
    with DDGS(timeout=25) as ddgs:
        for tema in temas:
            # Monta a query ex: "Radioterapia" (edital OR chamada) 2025..2026 site:.br
            query = f'"{tema}" {sufixo_busca}'
            try:
                time.sleep(2) # Respeita o servidor para não tomar block
                
                # Busca apenas os 2 melhores resultados
                resultados = list(ddgs.text(query, max_results=2))
                
                if resultados:
                    for r in resultados:
                        titulo = r.get('title', '')
                        link = r.get('href', '')
                        snippet = r.get('body', '')
                        
                        # Manda para a IA avaliar
                        analise = consultar_gemini(f"Título: {titulo}\nResumo: {snippet}", tipo_analise="busca")
                        
                        if analise:
                            tag_pdf = " 📄 <strong>[PDF]</strong>" if link.lower().endswith('.pdf') else ""
                            itens_html += f"""
                            <li style="margin-bottom: 8px; border-bottom: 1px dashed #eee; padding-bottom: 5px;">
                                <a href="{link}" style="color: #007bff; text-decoration: none; font-weight: 600;">{titulo}</a>{tag_pdf}
                                <div style="font-size: 12px; color: #444; margin-top: 2px;">🤖 {analise}</div>
                            </li>
                            """
            except Exception as e:
                print(f"Erro buscando '{tema}': {e}")
                continue
    return itens_html

def processar_eixo(nome_eixo, dados_eixo):
    """Gerencia a busca Brasil vs Mundo para um Eixo."""
    print(f"--- Processando Eixo: {nome_eixo} ---")
    lista_temas = dados_eixo["temas"]
    cor = dados_eixo["cor"]

    # Busca 1: Brasil (site:.br e termos em PT)
    html_br = _realizar_varredura_ddg(lista_temas, '(edital OR chamada OR processo seletivo) 2025..2026 site:.br')
    
    # Busca 2: Mundo (exclude .br e termos em EN)
    html_world = _realizar_varredura_ddg(lista_temas, '(grant OR funding OR phd position) 2025..2026 -site:.br')

    if not html_br and not html_world:
        return "" # Se não achou nada, não retorna caixa vazia

    # Monta o HTML do Eixo
    conteudo = f"""
    <div style="margin-bottom: 20px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: {cor}; color: white; padding: 10px; font-weight: bold;">{nome_eixo}</div>
        <div style="padding: 15px; background: #fff;">
    """
    if html_br:
        conteudo += f"<div style='margin-bottom:15px;'><div style='font-size:11px; font-weight:bold; color:#666; border-bottom:1px solid #eee;'>🇧🇷 BRASIL</div><ul style='padding-left:0; list-style:none;'>{html_br}</ul></div>"
    if html_world:
        conteudo += f"<div><div style='font-size:11px; font-weight:bold; color:#666; border-bottom:1px solid #eee;'>🌍 MUNDO</div><ul style='padding-left:0; list-style:none;'>{html_world}</ul></div>"
    
    return conteudo + "</div></div>"

# ==============================================================================
# 4. EXECUÇÃO PRINCIPAL (O Maestro)
# ==============================================================================

def executar_sentinela():
    session = criar_sessao_segura()
    
    # Passo 1: Sites Fixos
    html_fixos = ""
    for nome, url in SITES_FIXOS:
        status = verificar_site_fixo(nome, url, session) # Retorna tupla com dados
        html_fixos += f"""
        <div style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee;">
            {status[0]} <a href="{status[2]}" style="text-decoration:none; color:#2c3e50; font-weight:bold;">{status[1]}</a>
            <div style="font-size:12px; color:{status[4]}; margin-left:24px;">{status[3]}</div>
        </div>
        """

    # Passo 2: Busca nos Eixos (Itera sobre o dicionário de configuração)
    html_buscas = ""
    for nome_eixo, dados in EIXOS.items():
        html_buscas += processar_eixo(nome_eixo, dados)

    if not html_buscas:
        html_buscas = "<p style='text-align:center; color:#999;'>Nenhuma oportunidade relevante encontrada hoje.</p>"

    # Passo 3: Montagem Final do E-mail
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Segoe UI', sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <div style="background-color: #2c3e50; padding: 20px; text-align: center; color: white;">
                <h2 style="margin:0;">SENTINELA</h2>
                <p style="margin:5px 0 0; font-size:12px; color:#bdc3c7;">Monitoramento Diário</p>
            </div>
            <div style="padding: 20px;">
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 25px;">
                    <h3 style="margin:0 0 10px; font-size:12px; color:#666; text-transform:uppercase;">📍 Monitoramento Fixo</h3>
                    {html_fixos}
                </div>
                <h3 style="margin:0 0 15px; font-size:12px; color:#666; text-transform:uppercase;">🚀 Radar de Oportunidades</h3>
                {html_buscas}
            </div>
            <div style="background:#eee; padding:10px; text-align:center; font-size:10px; color:#777;">
                Gerado via GitHub Actions • Gemini Flash
            </div>
        </div>
    </body>
    </html>
    """

def enviar_email(html_body):
    if not EMAIL_ORIGEM or not SENHA_APP:
        print("Erro: Credenciais de e-mail não configuradas.")
        return

    msg = EmailMessage()
    msg['Subject'] = 'Sentinela: Relatório Diário'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = EMAIL_DESTINO
    msg.add_alternative(html_body, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ORIGEM, SENHA_APP)
        smtp.send_message(msg)
    print("E-mail enviado com sucesso!")

if __name__ == "__main__":
    relatorio = executar_sentinela()
    enviar_email(relatorio)
