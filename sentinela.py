import os
import smtplib
import time
import requests
from email.message import EmailMessage
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

# --- CONFIGURAÇÕES ---
EMAIL_ORIGEM = os.environ.get('EMAIL_REMETENTE')
SENHA_APP = os.environ.get('SENHA_APP')
EMAIL_DESTINO = EMAIL_ORIGEM

# --- SEUS EIXOS TEMÁTICOS (Listas Completas) ---
EIXO_NUCLEAR = [
    "Radioterapia", "Radiofármacos", "Medicina Nuclear", "Radioisótopos", 
    "Dosimetria", "Ciclotron", "Reator Nuclear", "Segurança Radiológica", 
    "AIEA", "Braquiterapia", "Acelerador Linear"
]

EIXO_IA_SAUDE = [
    "Inteligência Artificial saúde", "Machine Learning médica", "Visão Computacional exames", 
    "Processamento de Linguagem Natural saúde", "Deep Learning medicina", 
    "Algoritmos Preditivos saúde", "Radiômica", "Saúde 4.0", 
    "Telemedicina", "Big Data em Saúde"
]

EIXO_GESTAO = [
    "Complexo Econômico-Industrial da Saúde", "Avaliação de Tecnologias em Saúde", 
    "Inovação Assistencial", "Estudo Multicêntrico", "Pesquisa Clínica", 
    "Soberania Sanitária", "Proadi-SUS", "HealthTech"
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
    """Verifica sites oficiais (FAPERGS/DOU)."""
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return ("⚠️", f"{nome}: Erro {resp.status_code}", "orange")

        soup = BeautifulSoup(resp.content, 'html.parser')
        texto_site = soup.get_text().lower()
        
        termos_gerais = ["física médica", "edital", "aberto", "chamada", "bolsa"]
        encontradas = [p for p in termos_gerais if p in texto_site]
        
        if encontradas:
            return ("✅", f"{nome}: Termos detectados ({', '.join(encontradas[:3])})", "green")
        return ("ℹ️", f"{nome}: Nenhuma novidade detectada.", "#777")
    except Exception as e:
        return ("❌", f"{nome}: Falha de conexão.", "red")

def buscar_por_eixo(nome_eixo, lista_temas, cor_titulo):
    """
    Busca TODOS os temas da lista. 
    Só adiciona ao HTML se encontrar algo relevante.
    """
    itens_html = ""
    encontrou_algo = False
    
    print(f"--- Iniciando busca para: {nome_eixo} ---")

    with DDGS() as ddgs:
        for tema in lista_temas:
            # Estratégia: Combina o tema com "edital 2026" ou "chamada"
            # Isso filtra lixo e busca só oportunidades
            termo_busca = f'"{tema}" (edital OR chamada OR grant OR bolsa) 2026'
            
            try:
                # Pausa de 2 segundos para não ser bloqueado (Rate Limit)
                time.sleep(2) 
                
                # Pega até 2 resultados por palavra-chave
                results = list(ddgs.text(termo_busca, max_results=2))
                
                if results:
                    encontrou_algo = True
                    itens_html += f"<li style='margin-bottom: 8px;'><strong>{tema}:</strong><ul>"
                    
                    for r in results:
                        titulo = r.get('title', 'Sem título')
                        link = r.get('href', '#')
                        
                        # Tag visual para PDF
                        tag_extra = ""
                        if link.lower().endswith('.pdf'):
                            tag_extra = " <span style='background: #dc3545; color: white; font-size: 9px; padding: 2px 4px; border-radius: 3px;'>PDF</span>"
                        
                        itens_html += f"""
                            <li style="margin-top: 4px; font-size: 14px;">
                                <a href="{link}" style="color: #007bff; text-decoration: none;">{titulo}</a>{tag_extra}
                            </li>
                        """
                    itens_html += "</ul></li>"
                    print(f"  [+] Encontrado: {tema}")
                else:
                    print(f"  [.] Nada para: {tema}")

            except Exception as e:
                print(f"  [!] Erro ao buscar {tema}: {e}")
                continue

    # Se não achou nada no eixo inteiro, retorna vazio (para não poluir o e-mail)
    if not encontrou_algo:
        return ""

    # Se achou, monta a caixa bonita
    html_section = f"""
    <div style="margin-bottom: 20px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; font-family: sans-serif;">
        <div style="background-color: {cor_titulo}; color: white; padding: 10px; font-weight: bold;">
            {nome_eixo}
        </div>
        <div style="padding: 15px; background-color: #fff;">
            <ul style="padding-left: 20px; margin: 0; color: #333;">
                {itens_html}
            </ul>
        </div>
    </div>
    """
    return html_section

def executar_sentinela():
    session = criar_sessao_robusta()
    
    # 1. Sites Fixos
    fapergs = analisar_site_fixo("FAPERGS", "https://fapergs.rs.gov.br/editais-abertos", session)
    dou = analisar_site_fixo("DOU Pesquisa", "https://www.in.gov.br/leiturajornal", session)
    
    # 2. Busca Web (Agora varre tudo)
    # Nota: Isso vai demorar cerca de 1 a 2 minutos para rodar devido às pausas de segurança
    html_nuclear = buscar_por_eixo("☢️ Saúde Nuclear & Radioproteção", EIXO_NUCLEAR, "#6f42c1") # Roxo
    html_ia = buscar_por_eixo("💻 IA & Saúde Digital", EIXO_IA_SAUDE, "#0d6efd") # Azul
    html_gestao = buscar_por_eixo("🏥 Gestão & Inovação (HCPA/CEIS)", EIXO_GESTAO, "#198754") # Verde

    # Se nenhum eixo tiver resultado, mostra mensagem padrão
    if not html_nuclear and not html_ia and not html_gestao:
        mensagem_central = "<p style='text-align: center; color: #777;'>Nenhuma oportunidade específica encontrada na varredura web de hoje.</p>"
    else:
        mensagem_central = f"{html_nuclear}{html_ia}{html_gestao}"

    # 3. Monta E-mail
    html_final = f"""
    <!DOCTYPE html>
    <html>
    <head><style>body {{ font-family: Arial, sans-serif; }}</style></head>
    <body>
        <div style="max-width: 650px; margin: 0 auto; padding: 20px; border: 1px solid #eee;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px;">
                Sentinela: Radar Diário
            </h2>
            
            <h3 style="margin-top: 20px; font-size: 16px; color: #555;">📍 Portais Oficiais</h3>
            <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-size: 14px;">
                <p style="margin: 5px 0; color: {fapergs[2]};">
                    {fapergs[0]} <strong>FAPERGS:</strong> {fapergs[1].replace('FAPERGS:', '')}
                     <a href="https://fapergs.rs.gov.br/editais-abertos" style="color: #555;">[Link]</a>
                </p>
                <p style="margin: 5px 0; color: {dou[2]};">
                    {dou[0]} <strong>DOU:</strong> {dou[1].replace('DOU Pesquisa:', '')}
                     <a href="https://www.in.gov.br/leiturajornal" style="color: #555;">[Link]</a>
                </p>
            </div>

            <h3 style="margin-top: 30px; font-size: 16px; color: #555;">🌍 Varredura Web (Resultados Encontrados)</h3>
            {mensagem_central}

            <hr style="margin-top: 40px; border: 0; border-top: 1px solid #eee;">
            <p style="text-align: center; font-size: 11px; color: #999;">
                Monitoramento automático. Links marcados com <span style='background: #dc3545; color: white; padding: 0 2px;'>PDF</span> são documentos diretos.
            </p>
        </div>
    </body>
    </html>
    """
    return html_final

def enviar_email(html_content):
    if not EMAIL_ORIGEM or not SENHA_APP:
        print("Credenciais ausentes.")
        return

    msg = EmailMessage()
    msg['Subject'] = 'Sentinela: Radar de Oportunidades'
    msg['From'] = EMAIL_ORIGEM
    msg['To'] = EMAIL_DESTINO
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ORIGEM, SENHA_APP)
            smtp.send_message(msg)
        print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Erro no envio: {e}")

if __name__ == "__main__":
    resultado = executar_sentinela()
    enviar_email(resultado)
