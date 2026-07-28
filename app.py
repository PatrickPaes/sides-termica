import streamlit as st
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="Sides to Thermal", page_icon="🎬")

st.title("🎬 Gerador de Sides Contínuos (Inteligência de Texto)")
st.write("O código agora lê a página e identifica automaticamente onde o roteiro começa, ignorando cabeçalhos dinâmicos, datas e marcações de (CONTINUED).")

# --- PAINEL DE CONTROLE ---
st.markdown("### 🎛️ Configurações")
pular_paginas = st.number_input("Ignorar as primeiras N páginas (Call Sheet)", min_value=0, max_value=10, value=0)
ignorar_omissoes = st.checkbox("Cortar Cenas Omitidas (Marcadas com X grande)", value=True)

# Função inteligente para detectar o que é lixo visual (cabeçalho/rodapé)
def is_header_footer(text, y0, y1, page_height):
    text = text.strip().upper()
    if not text: 
        return True
    
    # Se o texto estiver bem no meio da página, com certeza é conteúdo do roteiro
    if y0 > page_height * 0.15 and y1 < page_height * 0.85:
        return False
    
    # Padrões clássicos de script que devemos cortar
    if "CONTINUED" in text: return True
    if re.match(r'^[\d\.]+[A-Z]?$', text): return True # Apenas números de página (ex: 2, 4A, 3.)
    if re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}$', text): return True # Datas (ex: 4/16/26)
    
    # Cores de revisão (Drafts)
    colors = ["WHITE", "BLUE", "PINK", "YELLOW", "GREEN", "GOLDENROD", "BUFF", "SALMON", "CHERRY", "TAN", "DOUBLE"]
    if any(color in text for color in colors): return True
    
    # Títulos curtos isolados no topo (ex: TRACKER 322)
    if len(text.split()) <= 5 and (y0 < page_height * 0.1):
        return True
        
    return False

uploaded_file = st.file_uploader("Suba o PDF dos sides", type="pdf")

if uploaded_file is not None:
    with st.spinner('Analisando o texto do roteiro...'):
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
                
                # 1. ANÁLISE DE TEXTO: Encontrar o verdadeiro início e fim do conteúdo
                blocks = page.get_text("blocks")
                valid_blocks = []
                
                for b in blocks:
                    if b[6] != 0: continue # Ignora imagens, apenas texto (tipo 0)
                    b_text = b[4]
                    if not is_header_footer(b_text, b[1], b[3], rect.height):
                        valid_blocks.append(b)
                
                if not valid_blocks:
                    continue # Se a página só tiver cabeçalho ou for em branco, pula.
                
                # Pega a coordenada Y do bloco mais alto e do bloco mais baixo
                content_y0 = max(0, min([b[1] for b in valid_blocks]) - 10) # 10 pts de respiro
                content_y1 = min(rect.height, max([b[3] for b in valid_blocks]) + 10)
                
                # 2. DETECTOR DE OMISSÕES (O "X")
                omission_rect = None
                if ignorar_omissoes:
                    drawings = page.get_drawings()
                    for d in drawings:
                        d_rect = d["rect"]
                        # Um 'X' de cena omitida geralmente cruza uma área grande da página
                        if d_rect.height > 60 and d_rect.width > 100:
                            if omission_rect is None:
                                omission_rect = d_rect
                            else:
                                omission_rect |= d_rect
                
                # 3. RECORTAR AS PARTES VÁLIDAS DA PÁGINA
                page_clips = []
                if omission_rect and ignorar_omissoes:
                    # Se houver texto válido ACIMA do 'X', guarda esse pedaço
                    if omission_rect.y0 > content_y0 + 20:
                        page_clips.append(fitz.Rect(0, content_y0, rect.width, omission_rect.y0))
                    # Se houver texto válido ABAIXO do 'X', guarda esse pedaço
                    if omission_rect.y1 < content_y1 - 20:
                        page_clips.append(fitz.Rect(0, omission_rect.y1, rect.width, content_y1))
                else:
                    # Se não tem omissão, guarda todo o conteúdo de texto descoberto
                    page_clips.append(fitz.Rect(0, content_y0, rect.width, content_y1))
                
                # 4. PREPARAR ESCALA PARA IMPRESSORA TÉRMICA
                for clip in page_clips:
                    clip = clip.normalize()
                    if clip.height > 20:
                        scale = TARGET_WIDTH_PTS / clip.width
                        scaled_height = clip.height * scale
                        
                        valid_clips.append({
                            "page": page,
                            "clip": clip,
                            "new_height": scaled_height
                        })
                        total_height += scaled_height

            # 5. GERAR O PDF FINAL
            if total_height == 0:
                st.error("❌ O arquivo final ficou vazio. Verifique se as páginas selecionadas possuem texto de roteiro legível.")
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

                st.success("✅ Roteiro gerado! Cabeçalhos limpos de forma inteligente.")
                
                st.download_button(
                    label="Baixar PDF Térmico 📥",
                    data=output_bytes,
                    file_name="Sides_Termicos_Inteligente.pdf",
                    mime="application/pdf"
                )
        
        input_pdf.close()
