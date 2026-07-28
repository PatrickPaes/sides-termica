import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="Sides to Thermal", page_icon="🎬")

st.title("🎬 Gerador de Sides Contínuos (Agrupamento Dinâmico)")
st.write("Versão refinada: Remove '(MORE)', ignora textos cruzados por 'X' e elimina espaços em branco residuais.")

# --- PAINEL DE CONTROLE ---
st.markdown("### 🎛️ Configurações")
pular_paginas = st.number_input("Ignorar as primeiras N páginas (Call Sheet)", min_value=0, max_value=10, value=0)
ignorar_omissoes = st.checkbox("Cortar Cenas Omitidas (Marcadas com X grande)", value=True)

# Função para caçar lixo visual
def is_header_footer(text, y0, y1, page_height):
    text_upper = text.strip().upper()
    if not text_upper: 
        return True
    
    # Nova regra: Remove o "(MORE)" em qualquer lugar da página
    if "(MORE)" in text_upper: 
        return True
    
    # Aplica regras estritas de cabeçalho/rodapé apenas nas margens extremas (top 12% e bottom 12%)
    is_margin = (y0 < page_height * 0.12) or (y1 > page_height * 0.88)
    
    if is_margin:
        if "CONTINUED" in text_upper: return True
        if re.match(r'^[\d\.]+[A-Z]?$', text_upper): return True # Numeração (ex: 82.)
        if re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}$', text_upper): return True # Datas
        
        # Filtro de cores de revisão e palavras chaves do cabeçalho
        colors_and_tags = ["WHITE", "BLUE", "PINK", "YELLOW", "GREEN", "GOLDENROD", "REV", "TIME", "TRACKER"]
        if any(tag in text_upper for tag in colors_and_tags): return True
        
        # Títulos curtos ou ruídos isolados na margem
        if len(text_upper.split()) <= 4: return True
        
    return False

uploaded_file = st.file_uploader("Suba o PDF dos sides", type="pdf")

if uploaded_file is not None:
    with st.spinner('Mapeando e agrupando o roteiro...'):
        input_pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        
        if input_pdf.is_encrypted or input_pdf.needs_pass:
            st.error("⚠️ O PDF está protegido por senha!")
        else:
            TARGET_WIDTH_PTS = 4 * 72 # 4 polegadas
            valid_clips = []
            total_height = 0
            
            for page_num in range(pular_paginas, len(input_pdf)):
                page = input_pdf[page_num]
                rect = page.rect
                
                # 1. MAPEAMENTO DE OMISSÕES ("X")
                omission_rect = None
                if ignorar_omissoes:
                    drawings = page.get_drawings()
                    for d in drawings:
                        d_rect = d["rect"]
                        # Procura apenas traços gigantes que formam o X (ignora linhas finas)
                        if d_rect.height > 100 and d_rect.width > 50:
                            if omission_rect is None:
                                omission_rect = d_rect
                            else:
                                omission_rect |= d_rect
                
                # 2. FILTRAR TEXTOS VÁLIDOS
                blocks = page.get_text("blocks")
                valid_blocks = []
                
                for b in blocks:
                    if b[6] != 0: continue # Ignora imagens, mantém só texto
                    b_text = b[4]
                    b_rect = fitz.Rect(b[:4])
                    
                    # Ignora se for cabeçalho, rodapé ou (MORE)
                    if is_header_footer(b_text, b_rect.y0, b_rect.y1, rect.height):
                        continue
                        
                    # MÁGICA: Se o texto estiver geograficamente DENTRO do "X", jogue fora!
                    center_y = (b_rect.y0 + b_rect.y1) / 2
                    if omission_rect and (omission_rect.y0 <= center_y <= omission_rect.y1):
                        continue
                        
                    valid_blocks.append(b)
                
                if not valid_blocks:
                    continue 
                
                # 3. CLUSTERING (AGRUPAR ILHAS DE TEXTO PARA MATAR BURACOS EM BRANCO)
                valid_blocks.sort(key=lambda b: b[1]) # Ordena de cima para baixo
                clusters = []
                current_cluster = [valid_blocks[0]]
                
                for i in range(1, len(valid_blocks)):
                    prev_b = current_cluster[-1]
                    curr_b = valid_blocks[i]
                    
                    # Se houver um buraco maior que 60 pontos entre um texto e outro, quebra o cluster
                    if curr_b[1] - prev_b[3] > 60:
                        clusters.append(current_cluster)
                        current_cluster = [curr_b]
                    else:
                        current_cluster.append(curr_b)
                clusters.append(current_cluster)
                
                # 4. CRIAR OS RECORTES APERTADOS
                for cluster in clusters:
                    cy0 = max(0, min(b[1] for b in cluster) - 10) # 10 pts de respiro acima
                    cy1 = min(rect.height, max(b[3] for b in cluster) + 10) # 10 pts de respiro abaixo
                    
                    clip = fitz.Rect(0, cy0, rect.width, cy1).normalize()
                    
                    if clip.height > 20:
                        scale = TARGET_WIDTH_PTS / clip.width
                        scaled_height = clip.height * scale
                        
                        valid_clips.append({
                            "page": page,
                            "clip": clip,
                            "new_height": scaled_height
                        })
                        total_height += scaled_height

            # 5. GERAR O ROLO CONTÍNUO
            if total_height == 0:
                st.error("❌ O arquivo final ficou vazio.")
            else:
                output_pdf = fitz.open()
                super_page = output_pdf.new_page(width=TARGET_WIDTH_PTS, height=total_height)
                
                y_offset = 0
                for item in valid_clips:
                    target_rect = fitz.Rect(0, y_offset, TARGET_WIDTH_PTS, y_offset + item["new_height"])
                    super_page.show_pdf_page(target_rect, input_pdf, item["page"].number, clip=item["clip"])
                    y_offset += item["new_height"]
                    
                output_bytes = output_pdf.write()
                output_pdf.close()

                st.success("✅ O roteiro foi costurado com sucesso, sem espaços em branco!")
                
                st.download_button(
                    label="Baixar PDF Térmico Final 📥",
                    data=output_bytes,
                    file_name="Sides_Termicos_Perfeitos.pdf",
                    mime="application/pdf"
                )
        
        input_pdf.close()
