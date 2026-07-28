import streamlit as st
import fitz  # PyMuPDF

st.set_page_config(page_title="Sides to Thermal", page_icon="🎬")

st.title("🎬 Gerador de Sides Contínuos (Térmica)")
st.write("Corta o Call Sheet, remove cabeçalhos e ignora cenas omitidas (com 'X' ou fundo escuro).")

uploaded_file = st.file_uploader("Suba o PDF dos sides", type="pdf")

if uploaded_file is not None:
    with st.spinner('Limpando e costurando o roteiro...'):
        input_pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        
        TARGET_WIDTH_PTS = 4 * 72 # 4 polegadas
        
        # Margens padrão para cortar os cabeçalhos/rodapés do roteiro
        HEADER_MARGIN = 90  # Corta o título da série e número da página
        FOOTER_MARGIN = 60
        
        valid_clips = []
        total_height = 0
        
        # 1. PULAR CALL SHEET: Começamos do índice 2 (ignora pág 1 e 2)
        for page_num in range(2, len(input_pdf)):
            page = input_pdf[page_num]
            rect = page.rect
            
            # Área útil inicial da página (sem cabeçalho e rodapé)
            content_rect = fitz.Rect(rect.x0, rect.y0 + HEADER_MARGIN, 
                                     rect.x1, rect.y1 - FOOTER_MARGIN)
            
            # 2. DETECTAR OMISSÕES ('X' ou Fundos Escuros)
            drawings = page.get_drawings()
            omission_rect = None
            
            for d in drawings:
                d_rect = d["rect"]
                # Heurística: Se um desenho (linha ou retângulo) ocupa mais de 20% da altura da página, 
                # assumimos que é uma marcação de cena omitida.
                if d_rect.height > (rect.height * 0.20):
                    if omission_rect is None:
                        omission_rect = d_rect
                    else:
                        omission_rect |= d_rect # Combina os retângulos se houver múltiplos traços
            
            # 3. RECORTAR A CENA VÁLIDA
            if omission_rect:
                # Se a omissão está na parte de CIMA da página
                if omission_rect.y0 < (rect.height / 2):
                    # Pegamos a parte de BAIXO (do fim da omissão até o rodapé)
                    clip_rect = fitz.Rect(content_rect.x0, omission_rect.y1, 
                                          content_rect.x1, content_rect.y1)
                # Se a omissão está na parte de BAIXO
                else:
                    # Pegamos a parte de CIMA (do cabeçalho até o início da omissão)
                    clip_rect = fitz.Rect(content_rect.x0, content_rect.y0, 
                                          content_rect.x1, omission_rect.y0)
            else:
                # Se não tem 'X', a página toda (dentro das margens) é válida
                clip_rect = content_rect
                
            # Verifica se sobrou conteúdo válido para imprimir (evita adicionar faixas vazias)
            if clip_rect.height > 20:
                # Escala o recorte para a largura de 4 polegadas da impressora
                scale = TARGET_WIDTH_PTS / clip_rect.width
                scaled_height = clip_rect.height * scale
                
                valid_clips.append({
                    "page": page,
                    "clip": clip_rect,
                    "new_height": scaled_height
                })
                total_height += scaled_height

        # 4. GERAR O PDF FINAL (O "Recibão")
        output_pdf = fitz.open()
        super_page = output_pdf.new_page(width=TARGET_WIDTH_PTS, height=total_height)
        
        y_offset = 0
        for item in valid_clips:
            # Onde este pedaço vai ser colado na nova super página
            target_rect = fitz.Rect(0, y_offset, TARGET_WIDTH_PTS, y_offset + item["new_height"])
            
            # Cola APENAS a parte válida (clip) da página original
            super_page.show_pdf_page(target_rect, input_pdf, item["page"].number, clip=item["clip"])
            
            y_offset += item["new_height"]
            
        output_bytes = output_pdf.write()
        output_pdf.close()
        input_pdf.close()

    st.success("Pronto! As omissões foram ignoradas e o roteiro está contínuo.")
    
    st.download_button(
        label="Baixar PDF Térmico 📥",
        data=output_bytes,
        file_name="Sides_Termicos_Formatados.pdf",
        mime="application/pdf"
    )