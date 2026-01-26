import os, time, smtplib
import google.generativeai as genai
from email.message import EmailMessage
from duckduckgo_search import DDGS

EMAIL = os.environ.get('EMAIL_REMETENTE')
SENHA = os.environ.get('SENHA_APP')
KEY = os.environ.get('GEMINI_API_KEY')
DESTINOS = [e.strip() for e in (os.environ.get('EMAIL_DESTINO') or EMAIL).replace('\n', ',').split(',') if e.strip()]

genai.configure(api_key=KEY)
MODELO = genai.GenerativeModel('gemini-1.5-flash')

ESTILO = """
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; color: #333; }
  .box { background: white; max-width: 700px; margin: 0 auto; border: 1px solid #ddd; border-radius: 5px; overflow: hidden; }
  .header { background: #333; color: white; padding: 20px; text-align: center; letter-spacing: 1px; }
  .header h3 { margin: 0; font-size: 18px; text-transform: uppercase; }
  .section { padding: 25px; border-bottom: 1px solid #eee; }
  .section-title { font-size: 13px; font-weight: bold; color: #444; text-transform: uppercase; margin-bottom: 15px; border-left: 4px solid #0056b3; padding-left: 10px; }
  ul { padding: 0; list-style: none; margin: 0; }
  li { margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #f0f0f0; }
  a { color: #0056b3; text-decoration: none; font-weight: 600; font-size: 15px; }
  .ai { font-size: 12px; color: #555; background: #f9f9f9; padding: 10px; border-radius: 4px; margin-top: 8px; border: 1px solid #eee; }
  .label-ai { font-weight: bold; color: #777; font-size: 10px; text-transform: uppercase; display: block; margin-bottom: 3px; }
  .pdf-tag { font-size: 9px; color: #d32f2f; border: 1px solid #d32f2f; padding: 1px 4px; border-radius: 3px; margin-left: 5px; vertical-align: middle; }
  .footer { background: #f5f5f5; padding: 15px; text-align: center; font-size: 11px; color: #999; border-top: 1px solid #ddd; }
"""

# --- ATENÇÃO: AQUI ESTÃO OS DADOS FALSOS PARA TESTE ---
# Eu criei manualmente o HTML simulando o que o robô faria.

RESULTADO_FAKE_BR = """
<li>
    <a href='https://www.gov.br/cnpq'>Edital Universal CNPq 2026 - Chamada para Projetos em Física Médica</a> <span class='pdf-tag'>PDF</span>
    <div class='ai'><span class='label-ai'>Análise IA:</span> Edital confirmado para financiamento de projetos de pesquisa em tecnologia nuclear com vigência até dezembro de 2026.</div>
</li>
<li>
    <a href='https://www.fapergs.rs.gov.br'>Bolsa de Iniciação Científica FAPERGS - Saúde Digital</a>
    <div class='ai'><span class='label-ai'>Análise IA:</span> Chamada aberta para bolsistas de graduação atuarem em projetos de Inteligência Artificial aplicada à saúde no RS.</div>
</li>
"""

RESULTADO_FAKE_WORLD = """
<li>
    <a href='https://www.nih.gov'>NIH Grant for Radiotherapy Quality Assurance</a>
    <div class='ai'><span class='label-ai'>Análise IA:</span> Oportunidade de financiamento internacional para desenvolvimento de novos protocolos de dosimetria, submissões até maio de 2026.</div>
</li>
"""

if __name__ == "__main__":
    print(">>> MODO DE TESTE: Gerando e-mail com dados fictícios...")

    # Em vez de buscar na web, usamos as variáveis falsas acima
    br = RESULTADO_FAKE_BR
    world = RESULTADO_FAKE_WORLD

    corpo = ""
    if br: corpo += f"<div class='section'><div class='section-title'>BRASIL | Oportunidades Nacionais (SIMULAÇÃO)</div><ul>{br}</ul></div>"
    if world: corpo += f"<div class='section'><div class='section-title'>INTERNACIONAL | Oportunidades Globais (SIMULAÇÃO)</div><ul>{world}</ul></div>"
    
    html_final = f"""
    <html><head><style>{ESTILO}</style></head>
    <body>
        <div class='box'>
            <div class='header'><h3>SISTEMA DE MONITORAMENTO SENTINELA</h3></div>
            {corpo}
            <div class='footer'>Relatório de Teste de Layout</div>
        </div>
    </body></html>
    """
    
    print(f">>> Enviando para: {', '.join(DESTINOS)}")
    msg = EmailMessage()
    msg['Subject'], msg['From'], msg['To'] = 'TESTE: Visualização do Sistema Sentinela', EMAIL, ', '.join(DESTINOS)
    msg.add_alternative(html_final, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL, SENHA)
        smtp.send_message(msg)
    print("✅ E-mail de teste enviado com sucesso!")
