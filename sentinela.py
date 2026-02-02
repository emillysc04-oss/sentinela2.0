import os
import json
import requests
import time

# --- A LISTA DE OURO (42 ITENS) ---
SITES_ALVO = [
    # 1. Abrangentes Brasil
    "site:gov.br", "site:edu.br", "site:org.br", "site:b.br",
    
    # 2. Rio Grande do Sul e Instituições Focais
    "site:fapergs.rs.gov.br", "site:hcpa.edu.br", "site:ufrgs.br", "site:ufcspa.edu.br",
    "site:afimrs.com.br", "site:sgr.org.br", "site:amrigs.org.br",
    
    # 3. Outros Estados (Fomento)
    "site:fapesc.sc.gov.br", "site:fara.pr.gov.br", "site:fapesp.br",
    
    # 4. Internacionais (Física Médica & Saúde)
    "site:iaea.org", "site:who.int", "site:nih.gov", "site:europa.eu", "site:nsf.gov",
    "site:aapm.org", "site:estro.org", "site:astro.org", "site:rsna.org",
    "site:iomp.org", "site:efomp.org", "site:snmmi.org",
    
    # 5. Educação Global & Preprints
    "site:edu", "site:ac.uk", "site:arxiv.org",
    
    # 6. Revistas e Publicações (Call for Papers)
    "site:ieee.org", "site:nature.com", "site:science.org", "site:sciencedirect.com",
    "site:iop.org", "site:frontiersin.org", "site:mdpi.com", "site:wiley.com",
    "site:springer.com", "site:thelancet.com",
    
    # 7. Hospitais de Excelência
    "site:einstein.br", "site:hospitalsiriolibanes.org.br", "site:moinhosdevento.org.br"
]

def buscar_google_elite():
    print("🚀 SENTINELA (Modo Varredura Completa - 42 Fontes) INICIADO...\n")
    
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("❌ ERRO CRÍTICO: Chave SERPER_API_KEY não encontrada no GitHub Secrets.")
        return

    # Termos da busca (o que queremos encontrar nesses sites)
    # Procuramos por editais, bolsas ou chamadas abertas
    query_base = '(edital OR chamada OR "call for papers" OR bolsa OR grant) ("física médica" OR radioterapia OR "medical physics")'
    
    url = "https://google.serper.dev/search"
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    total_encontrado = 0
    
    # --- DIVISÃO EM BLOCOS (CHUNKS) ---
    # O Google não aguenta 42 sites de uma vez. Vamos mandar de 8 em 8.
    tamanho_bloco = 8
    blocos = [SITES_ALVO[i:i + tamanho_bloco] for i in range(0, len(SITES_ALVO), tamanho_bloco)]

    print(f"📋 A lista de 42 sites foi dividida em {len(blocos)} rodadas de busca para não travar.\n")

    for i, bloco in enumerate(blocos):
        # Monta a string: (site:A OR site:B OR site:C)
        filtro_sites = " OR ".join(bloco)
        query_final = f"{query_base} ({filtro_sites})"
        
        print(f"🔎 Rodada {i+1}/{len(blocos)}: Verificando {len(bloco)} sites...")
        # print(f"   Sites: {bloco}") # Descomente se quiser ver os sites rodando

        payload = json.dumps({
            "q": query_final,
            "num": 5,        # Pega os 5 melhores de cada bloco
            "tbs": "qdr:m",  # Apenas último mês (m) ou semana (w)
            "gl": "br"
        })

        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            dados = response.json()
            
            items = dados.get("organic", [])
            
            if items:
                print(f"   ✅ Encontrei {len(items)} oportunidades neste bloco:")
                for item in items:
                    print(f"      📄 {item.get('title')}")
                    print(f"      🔗 {item.get('link')}")
                    print(f"      📅 {item.get('date', 'Data não informada')}")
                    print("      ---")
                total_encontrado += len(items)
            else:
                print("   📭 Nenhuma novidade recente nestes sites.")

            # Pausa rápida para não ser bloqueado por excesso de velocidade
            time.sleep(1)

        except Exception as e:
            print(f"❌ Erro na conexão: {e}")
        
        print("-" * 30)

    print(f"\n✨ VARREDURA FINALIZADA. Total de links encontrados: {total_encontrado}")

if __name__ == "__main__":
    buscar_google_elite()
