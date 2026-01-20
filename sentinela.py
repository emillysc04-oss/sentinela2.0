import os
import time
import smtplib
import google.generativeai as genai
from email.message import EmailMessage
from duckduckgo_search import DDGS

# ==============================================================================
# 1. CONFIGURAÇÕES
# ==============================================================================

EMAIL_ORIGEM  = os.environ.get('EMAIL_REMETENTE')
SENHA_APP     = os.environ.get('SENHA_APP')
GEMINI_KEY    = os.environ.get('GEMINI_API_KEY')

# --- NOVA LÓGICA DE LISTA (Lê do arquivo txt) ---
ARQUIVO_EMAILS = "lista_emails.txt"
LISTA_DESTINOS = []

# 1. Tenta ler o arquivo se ele existir
if os.path.exists(ARQUIVO_EMAILS):
    with open(ARQUIVO_EMAILS, "r", encoding="utf-8") as f:
        # Lê linha a linha, remove espaços e ignora linhas com # (comentários)
        LISTA_DESTINOS = [
            linha.strip() 
            for linha in f.readlines() 
            if linha.strip() and not linha.strip().startswith("#")
        ]
else:
    print(f"Aviso: Arquivo {ARQUIVO_EMAILS} não encontrado.")

# 2. Se a lista estiver vazia (ou arquivo não existir), manda só para o dono
if not LISTA_DESTINOS:
    print("Usando e-mail de origem como fallback.")
    LISTA_DESTINOS = [EMAIL_ORIGEM]

print(f"Destinatários carregados: {len(LISTA_DESTINOS)}")

# Configuração da IA
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    MODELO_IA = genai.GenerativeModel('gemini-1.5-flash')
else:
    MODELO_IA = None

# Eixos Temáticos
EIXOS = {
    "☢️ Nuclear & Física Médica": {
        "cor": "#8e44ad", 
        "temas": ["Radioterapia", "Radiofármacos", "Medicina Nuclear", "Física Médica", "Dosimetria", "Proteção Radiológica"]
    },
    "💻 Inteligência Artificial": {
        "cor": "#2980b9", 
        "temas": ["Inteligência Artificial saúde", "Machine Learning médica", "Deep Learning medicina", "Saúde Digital", "Big Data em Saúde"]
    },
    "🏥 Gestão & Fomento": {
        "cor": "#27ae60", 
        "temas": ["Avaliação de Tecnologias em Saúde", "Inovação Hospitalar", "HealthTech", "CNPq", "FAPERGS", "Ministério da Saúde", "Proadi-SUS"]
    }
}

# ==============================================================================
# 2. CÉREBRO (IA)
# ==============================================================================

def consultar_gemini(titulo, resumo):
    if not MODELO_IA: return None

    prompt = f"""
    Analise este resultado de busca:
    Título: {titulo}
    Resumo: {resumo}

    TAREFA:
    Você é um radar de oportunidades acadêmicas.
    1. O link parece ser um EDITAL, BOLSA, GRANT, CHAMADA PÚBLICA ou VAGA DE PESQUISA vigente?
    2. Ignore: Notícias genéricas, vendas, wikis e redes sociais.

    RESPOSTA:
    - Se irrelevante: "NÃO".
    - Se relevante: Resumo de 1 frase.
    """
    try:
        response = MODELO_IA.generate_content(prompt)
        txt = response.text.strip()
        if "NÃO" in txt.upper() or len(txt) < 5: return None
        return txt
    except: return None

# ==============================================================================
# 3. MOTOR DE BUSCA
# ==============================================================================

def _varrer_ddg(temas, sufixo_query):
    itens_html = ""
    with DDGS(timeout=30) as ddgs:
        for tema in temas:
            query = f'"{tema}" {sufixo_query}'
            try:
                time.sleep(2)
                resultados = list(ddgs.text(query, max_results=2))
                
                if resultados:
                    for r in resultados:
                        titulo = r.get('title', 'Sem título')
                        link = r.get('href', '#')
                        snippet = r.get('body', '')
                        
                        analise = consultar_gemini(titulo, snippet)
                        
                        if analise:
                            tag_pdf = " 📄 <strong>[PDF]</strong>" if link.lower().endswith('.pdf') else ""
                            itens_html += f"""
                            <li style="margin-bottom: 10px; border-bottom: 1px dashed #eee; padding-bottom: 8px;">
                                <a href="{link}" style="color: #007bff; text-decoration: none; font-weight: 600; font-size: 14px;">{titulo}</a>{tag_pdf}
                                <div style="font-size: 12px; color: #444; margin-top: 4px; background-color: #f9f9f9; padding: 5px; border-radius: 4px;">
                                    🤖 {analise}
                                </div>
                            </li>
                            """
            except Exception as e:
                print(f"Erro buscando '{tema}': {e}")
                continue
    return itens_html

def processar_eixo(nome_eixo, dados):
    print(f"--- Processando: {nome_eixo} ---")
    html_br = _varrer_ddg(dados["temas"], '(edital OR chamada OR seleção OR bolsa) 2025..2026 site:.br')
    html_world = _varrer_ddg(dados["temas"], '(grant OR funding OR phd position OR call for papers) 2025..2026 -site:.br')

    if not html_br and not html_world: return ""

    conteudo = f"""
    <div style="margin-bottom: 25px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; font-family: sans-serif;">
        <div style="background-color: {dados['cor']}; color: white; padding: 10px 15px; font-weight: bold; font-size: 15px;">
            {nome_eixo}
        </div>
        <div style="padding: 15px; background: #fff;">
    """
    if html_br:
        conteudo += f"<div style='margin-bottom:20px;'><div style='font-size:11px; font-weight:800; color:#777; border-bottom:2px solid #eee; margin-bottom:10px;'>🇧🇷 BRASIL</div><ul style='padding-left:0; list-style:none; margin:0;'>{html_br}</ul></div>"
    if html_world:
        conteudo += f"<div><div style='font-size:11px; font-weight:800; color:#777; border-bottom:2px solid #eee; margin-bottom:10px;'>🌍 INTERNACIONAL</div><ul style='padding-left:0; list-style:none; margin:0;'>{html_world}</ul></div>"
        
    return conteudo + "</div></div>"

# ==============================================================================
# 4. EXECUÇÃO E ENVIO
# ==============================================================================

def executar_sentinela():
    corpo_email = ""
    for nome, dados in EIXOS.items():
        corpo_email += processar_eixo(nome, dados)

    if not corpo_email:
        corpo_email = """
        <div style="text-align: center; padding: 40px; color: #999;">
            <p><strong>Nenhuma oportunidade relevante detectada hoje.</strong></p>
            <p style="font-size: 12px;">Os filtros de IA analisaram as buscas e descartaram resultados de baixa qualidade.</p>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4; padding: 20px; margin: 0;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            <div style="background-color: #2c3e50; padding: 25px; text-align: center;">
                <h1 style="color: #fff; margin: 0; font-size: 24px; letter-spacing: 1px;">SENTINELA</h1>
                <p style="color: #bdc3c7; margin: 5px 0 0 0; font-size: 13px;">Radar de Oportunidades com IA</p>
            </div>
            <div style="padding: 30px 20px;">
                {corpo_email}
            </div>
            <div style="background-color: #ecf0f1; padding: 15px; text-align: center; font-size: 11px; color: #7f8c8d;">
                Gerado via GitHub Actions • Gemini Flash
            </div>
        </div>
    </body>
    </html>
    """

def enviar_email(html_body):
    if not EMAIL_ORIGEM or not SENHA_APP:
        print("Erro: Credenciais ausentes.")
        return

    destinatarios_str = ', '.join(LISTA_DESTINOS)
    print(f"Enviando para: {destinatarios_str}")

    msg = EmailMessage()
    msg['Subject'] = 'Sentinela: Radar Diário'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = destinatarios_str
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ORIGEM, SENHA_APP)
            smtp.send_message(msg)
        print("E-mail enviado!")
    except Exception as e:
        print(f"Erro ao enviar: {e}")

if __name__ == "__main__":
    relatorio = executar_sentinela()
    enviar_email(relatorio)
