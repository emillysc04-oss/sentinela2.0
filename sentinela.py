import os, time, smtplib, json, warnings
import google.generativeai as genai
import gspread
from email.message import EmailMessage

# --- 0. CONFIGURAÇÕES INICIAIS ---
warnings.filterwarnings("ignore")
os.environ['GRPC_VERBOSITY'] = 'ERROR'

EMAIL = os.environ.get('EMAIL_REMETENTE')
SENHA = os.environ.get('SENHA_APP')
KEY = os.environ.get('GEMINI_API_KEY')
SHEETS_JSON = os.environ.get('GOOGLE_CREDENTIALS')

# --- 1. CONFIGURANDO O GEMINI COM "OLHOS" (GOOGLE SEARCH) ---
genai.configure(api_key=KEY)

# Aqui está o segredo: tools='google_search_retrieval'
# Usamos o modelo 002 que é mais obediente para ferramentas
MODELO = genai.GenerativeModel(
    'models/gemini-1.5-flash-002', 
    tools='google_search_retrieval'
)

# --- 2. LEITURA DA PLANILHA ---
def obter_lista_emails():
    lista_final = []
    if SHEETS_JSON:
        try:
            credenciais = json.loads(SHEETS_JSON)
            gc = gspread.service_account_from_dict(credenciais)
            try:
                sh = gc.open("Sentinela Emails")
            except:
                sh = gc.open("Formulário sem título (respostas)")
            valores = sh.sheet1.col_values(3)
            for email in valores:
                if '@' in email and '.' in email:
                    lista_final.append(email.strip())
            print(f">>> Destinatários: {len(lista_final)}")
        except Exception as e:
            print(f"⚠️ Erro Planilha: {e}")
    if not lista_final: lista_final = [EMAIL]
    return lista_final

DESTINOS = obter_lista_emails()

# --- 3. DESIGN HCPA ---
ESTILO = """
  body { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background: #fff; padding: 30px; color: #404040; line-height: 1.6; }
  .box { max-width: 700px; margin: 0 auto; border-top: 6px solid #009586; }
  .header { padding: 30px 0; text-align: center; border-bottom: 1px solid #eee; }
  .header h3 { margin: 0; font-size: 22px; color: #009586; font-weight: 300; letter-spacing: 0.5px; text-transform: uppercase; }
  .section { padding: 30px 0; border-bottom: 1px solid #f0f0f0; }
  .ai { font-size: 14px; color: #555; background: #f8fcfb; padding: 15px; border-left: 3px solid #009586; margin-top: 5px; }
  .footer { padding: 40px 0; text-align: center; font-size: 12px; color: #999; border-top: 1px solid #eee; }
  a { color: #009586; font-weight: bold; text-decoration: none; }
"""

# --- 4. A INTELIGÊNCIA PURA (SEM DUCKDUCKGO) ---
def gerar_relatorio_gemini():
    print(">>> Solicitando pesquisa direta ao Google via Gemini...")
    
    # Este é o prompt que imita o que você fez no chat
    prompt = """
    Atue como um Especialista em Fomento à Pesquisa do HCPA (Hospital de Clínicas de Porto Alegre).
    
    Sua tarefa: Pesquise agora no Google Search por editais, chamadas públicas, bolsas e grants ABERTOS e VIGENTES para 2025 e 2026 nas seguintes áreas:
    1. Física Médica e Radioterapia
    2. Medicina Nuclear
    3. Inteligência Artificial aplicada à Saúde
    4. Inovação Hospitalar (CNPq, FAPERGS, MS, Proadi-SUS)
    
    REGRAS DE RESPOSTA (IMPORTANTE):
    - Você DEVE fornecer o LINK direto para cada edital encontrado.
    - Crie um resumo HTML formatado.
    - Use a estrutura: <li><a href="LINK">TITULO</a><br>Resumo: ...</li>
    - Separe em duas seções: <h3>Oportunidades Nacionais</h3> e <h3>Oportunidades Internacionais</h3>.
    - Se não encontrar links diretos, avise.
    """
    
    try:
        # Aumentamos a criatividade (temperature) para ele explorar mais
        resposta = MODELO.generate_content(prompt)
        
        # O Gemini com Search retorna o texto com links embutidos ou no metadata.
        # Vamos pegar o texto renderizado que ele gera.
        conteudo = resposta.text
        
        # Pequeno ajuste para garantir que virou HTML (caso ele mande Markdown)
        conteudo = conteudo.replace("```html", "").replace("```", "")
        
        return conteudo
    except Exception as e:
        print(f"Erro na geração Gemini: {e}")
        return "<p>Erro ao conectar com a Inteligência Google.</p>"

# --- 5. EXECUÇÃO ---
if __name__ == "__main__":
    html_conteudo = gerar_relatorio_gemini()
    
    # Montagem Final
    html_final = f"""
    <html><head><style>{ESTILO}</style></head>
    <body>
        <div class='box'>
            <div class='header'>
                <h3>SISTEMA SENTINELA (GOOGLE NATIVE)</h3>
                <p>Relatório de Inteligência</p>
            </div>
            <div class='section'>
                {html_conteudo}
            </div>
            <div class='footer'>
                Hospital de Clínicas de Porto Alegre<br>
                Powered by Gemini Grounding
            </div>
        </div>
    </body></html>
    """
    
    print(f">>> Enviando para {len(DESTINOS)} destinatários via Bcc.")
    msg = EmailMessage()
    msg['Subject'], msg['From'], msg['To'] = 'Sistema Sentinela: Relatório Diário', EMAIL, EMAIL
    msg['Bcc'] = ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
    print("✅ E-mail enviado!") 
