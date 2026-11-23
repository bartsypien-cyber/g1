import streamlit as st
import pandas as pd
import time
import os
import json
from src.data_processing import (
    load_ai_model, 
    prepare_knowledge_base, 
    categorize_nlp, 
    update_ai_dictionary
)
from src.excel_utils import generate_g1_export, generate_dict_export

st.set_page_config(page_title="G1 AI Generator", layout="wide", initial_sidebar_state="expanded")
st.markdown("<style>header {visibility: hidden;}</style>", unsafe_allow_html=True)

LANGS = {
    '🇵🇱 Polski': {
        'main_title': "⚙️ G1 Key-In loss Lv1/Lv2 generator",
        'step1_h': "1. Wgraj plik źródłowy", 
        'up_dw': "Wgraj aktualny plik G1 do przetworzenia (.xlsx)",
        'btn_start': "Rozpocznij proces ➔", 'step2_h': "2. Ustawienia logiki biznesowej",
        'sel_col': "Wskaż kolumnę określającą typ postoju:", 'sel_type': "Wybierz typy postojów do kategoryzacji (np. BM, PD):",
        'btn_back': "⬅️ Wróć", 'btn_nlp': "Rozpocznij pracę silnika NLP ➔",
        'warn_type': "Wybierz minimum jeden typ postoju.", 'step3_h': "3. Analiza Sieci Neuronowej w toku",
        'i3_1': "Krok 3.1: Wczytywanie ontologii JSON oraz reguł Lv1/Lv2/Unit...",
        'i3_2': "Krok 3.2: Ładowanie modelu NLP i wektoryzacja baz...",
        'i3_3': "Krok 3.3: Kontekstowa kategoryzacja logów (Pobieranie powiązań)...",
        'i3_5': "Krok 3.5: Składanie pliku wynikowego...",
        'ai_success': "Procesy analityczne zakończone pomyślnie!", 'step4_h': "4. Podsumowanie i Eksport",
        'm1': "Skategoryzowane wiersze", 'm2': "Średnia pewność", 'm3': "Pewne trafienia",
        'dl_panel': "### 📥 Panel Pobierania Danych", 'dl_g1': "📥 Pobierz Skategoryzowany Plik (Czysty Raport)",
        'btn_reset': "🔄 Zakończ i zresetuj sesję"
    }
}

if 'language' not in st.session_state: st.session_state.language = '🇵🇱 Polski'
if 'step' not in st.session_state: st.session_state.step = 1
if 'df_dw' not in st.session_state: st.session_state.df_dw = None
if 'global_progress' not in st.session_state: st.session_state.global_progress = 0

t = LANGS[st.session_state.language]

st.title(t["main_title"])
st.progress(int(st.session_state.global_progress))
st.markdown("---")

if st.session_state.step == 1:
    st.session_state.global_progress = 10
    st.subheader(t["step1_h"])
    dw_file = st.file_uploader(t["up_dw"], type=['xlsx'])
        
    if dw_file:
        st.session_state.global_progress = 25
        if st.button(t["btn_start"], type="primary"):
            try:
                st.session_state.df_dw = pd.read_excel(dw_file, sheet_name='Raw_raw')
            except ValueError:
                st.session_state.df_dw = pd.read_excel(dw_file, sheet_name=0)
            st.session_state.step = 2
            st.rerun()

elif st.session_state.step == 2:
    st.session_state.global_progress = 35
    st.subheader(t["step2_h"])
    columns = st.session_state.df_dw.columns.tolist()
    guess_col = 'Loss Name' if 'Loss Name' in columns else columns[0]
    
    type_col = st.selectbox(t["sel_col"], columns, index=columns.index(guess_col))
    unique_types = st.session_state.df_dw[type_col].dropna().unique().tolist()
    selected_types = st.multiselect(t["sel_type"], unique_types, default=[typ for typ in unique_types if str(typ).upper() in ['BM', 'PD']])
    
    colA, colB = st.columns([1, 4])
    with colA:
        if st.button(t["btn_back"], use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with colB:
        if st.button(t["btn_nlp"], type="primary", use_container_width=True):
            if selected_types:
                st.session_state.type_col = type_col
                st.session_state.selected_types = selected_types
                st.session_state.step = 3
                st.rerun()
            else:
                st.warning(t["warn_type"])

elif st.session_state.step == 3:
    st.session_state.global_progress = 40
    st.subheader(t["step3_h"])
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    status_text.info(t["i3_1"])
    model = load_ai_model()
    progress_bar.progress(30)
    
    status_text.info(t["i3_2"])
    mask, trained_model, _, _, _ = prepare_knowledge_base(model, st.session_state.df_dw, st.session_state.type_col, st.session_state.selected_types)
    progress_bar.progress(60)
    
    status_text.info(t["i3_3"])
    df_dw, mean_score, confident = categorize_nlp(st.session_state.df_dw, mask, trained_model, None, None, None, None)
    progress_bar.progress(90)

    status_text.info(t["i3_5"])
    st.session_state.df_dw = df_dw
    st.session_state.mask = mask
    st.session_state.mean_score = mean_score
    st.session_state.confident = confident
    
    progress_bar.progress(100)
    st.session_state.global_progress = 100
    status_text.success(t["ai_success"])
    time.sleep(0.5)
    st.session_state.step = 4
    st.rerun()

elif st.session_state.step == 4:
    st.subheader(t["step4_h"])
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t["m1"], int(st.session_state.mask.sum()))
    col2.metric(t["m2"], f"{st.session_state.mean_score:.1f}%")
    col3.metric(t["m3"], int(st.session_state.confident))
    
    st.markdown("---")
    st.markdown(t["dl_panel"])
    
    g1_bytes_ready = generate_g1_export(st.session_state.df_dw)
    
    st.download_button(t["dl_g1"], data=g1_bytes_ready, file_name="G1_AI_Wypelnione.xlsx", type="primary")
        
    st.markdown("---")
    if st.button(t["btn_reset"]):
        st.session_state.clear()
        st.rerun()