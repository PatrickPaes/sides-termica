import streamlit as st
import fitz  # PyMuPDF

st.set_page_config(page_title="Sides to Thermal", page_icon="🎬")

st.title("🎬 Gerador de Sides Contínuos (Modo Seguro)")
st.write("Use os controles abaixo para ajustar o corte do roteiro.")

# --- PAINEL DE CONTROLE NA TELA ---
st.markdown("### 🎛️ Configurações de Corte")
pular_paginas = st.number_input("Ignorar as primeiras N páginas (Ex: Call Sheet)", min_value=0, max_value=10, value=0)
remover_cabecalhos = st.checkbox("Cortar Cabeçalhos e Rodapés", value=True)
ignorar_omissoes = st.checkbox("Cortar Cenas Omitidas (Marcadas com X)", value=False)
# (Deixei "Cortar Cenas Omitidas" desligado por padrão para você testar se o PDF básico funciona)

uploaded_file = st.file_uploader("Suba o PDF dos sides", type="pdf")

if uploaded_file is not None:
    with st.spinner('Processando o roteiro...'):
        input_pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        
        # 1. Checagem de Proteção do PDF
        if input_pdf.is_encrypted or input_pdf.needs_pass:
            st.error("⚠️ O PDF está protegido por senha ou criptografia! O sistema está bloqueado de ler o conteúdo.")
        else:
            TARGET_WIDTH_PTS = 4 * 72 # 4 polegadas
            
            # Margens (se a checkbox estiver ativada)
            HEADER_MARGIN = 90 if remover_cabecalhos else 0
            FOOTER_MARGIN = 60 if remover_cabecalhos else 0
            
            valid_clips = []
            total_height = 0
            
            # O laço agora começa a partir da página que você escolheu no menu
            for page_num in range(pular_paginas, len(input_pdf)):
                page = input_pdf[page_num]
                rect = page.rect
                
                # Define a área útil e "normaliza" para garantir que a matemática não fique negativa
                content_rect = fitz.Rect(rect.x0, rect.y0 + HEADER_MARGIN, 
                                         rect.x1, rect.y1 - FOOTER_MARGIN).normalize()
                
                clip_rect = content_rect
                
                # Se a função de caçar 'X' estiver ligada
                if ignorar_omissoes:
                    drawings = page.get_drawings()
                    omission_rect = None
                    
                    for d in drawings:
                        d_rect = d["rect"]
                        # Procura formas grandes
                        if d_rect.height > (rect.height * 0.20):
                            if omission_rect is None:
                                omission_rect = d_rect
                            else:
                                omission_rect |= d_rect
                    
                    if omission_rect:
                        # Corta a parte de cima ou de baixo baseado na posição da omissão
                        if omission_rect.y0 < (rect.height / 2):
                            clip_rect = fitz.Rect(content_rect.x0, omission_rect.y1, 
                                                  content_rect.x1, content_rect.y1).normalize()
                        else:
                            clip_rect = fitz.Rect(content_rect.x0, content_rect.y0, 
                                                  content_rect.x1, omission_rect.y0).normalize()
                
                # Garante que sobrou um pedaço de página com mais de 20 pontos de altura
                if clip_rect.height > 20:
                    scale = TARGET_WIDTH_PTS / clip_rect.width
                    scaled_height = clip_rect.height * scale
                    
                    valid_clips.append({
                        "page": page,
                        "clip": clip_rect,
                        "new_height": scaled_height
                    })
                    total_height += scaled_height

            # Se o código acabou cortando 100% do PDF por engano
            if total_height == 0:
                st.error("❌ Erro: O documento final ficou vazio! Tente desativar a opção de cortar cabeçalhos ou cenas omitidas.")
            else:
                # Gera o Super PDF
                output_pdf = fitz.open()
                super_page = output_pdf.new_page(width=TARGET_WIDTH_PTS, height=total_height)
                
                y_offset = 0
                for item in valid_clips:
                    target_rect = fitz.Rect(0, y_offset, TARGET_WIDTH_PTS, y_offset + item["new_height"])
                    super_page.show_pdf_page(target_rect, input_pdf, item["page"].number, clip=item["clip"])
                    y_offset += item["new_height"]
                    
                output_bytes = output_pdf.write()
                output_pdf.close()

                st.success("✅ Roteiro gerado com sucesso!")
                
                st.download_button(
                    label="Baixar PDF Térmico 📥",
                    data=output_bytes,
                    file_name="Sides_Termicos_Seguro.pdf",
                    mime="application/pdf"
                )
        
        input_pdf.close()
