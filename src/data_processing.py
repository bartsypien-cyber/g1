import pandas as pd
import numpy as np
import re
import os
import json
import streamlit as st
import torch
from sentence_transformers import SentenceTransformer, util
import warnings

warnings.filterwarnings("ignore")

DEFAULT_UNITS = [
    "Stacking", "Other", "Monoframe/ EP Welding", "BusBar/ Lead Welding",
    "Resin Injection", "Unloader", "Cell Loader", "Cell Inspection",
    "EOL", "Cutting"
]

def isolate_problem_description(row):
    loss_name = str(row.get('Loss Name', '')) if pd.notna(row.get('Loss Name')) else ""
    det_loss = str(row.get('Detailed Loss Name', '')) if pd.notna(row.get('Detailed Loss Name')) else ""
    note = str(row.get('Loss Note', '')) if pd.notna(row.get('Loss Note')) else ""
    remark = str(row.get('Remark', '')) if pd.notna(row.get('Remark')) else ""
    
    raw_text = f"{note} {remark}".strip()
    split_pattern = re.compile(r'(?:\br\s*:|\baction\s*:|\bc\s*:\s*(?:wymiana|sprawdzenie|czyszczenie|poprawa|zmiana|reset|restart|wyciągnięcie|usunięcie|ponowienie|odłożenie))', re.IGNORECASE)
    parts = split_pattern.split(raw_text, maxsplit=1)
    
    prob_part = parts[0].strip().lower()
    return f"{loss_name.lower()} {det_loss.lower()} {prob_part}".strip()

@st.cache_resource
def load_ai_model():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'data_driven_ontology.json')
    rules_path = os.path.join(base_dir, 'Reguly_AI.xlsx')
    unit_rules_path = os.path.join(base_dir, 'Reguly_Unit.xlsx')
    
    if not os.path.exists(json_path):
        st.error(f"KRYTYCZNY BŁĄD: Brak pliku 'data_driven_ontology.json' w {base_dir}")
        st.stop()
        
    with open(json_path, 'r', encoding='utf-8') as f:
        ontology = json.load(f)
        
    if not os.path.exists(rules_path):
        df_rules = pd.DataFrame(columns=['Slowo_Klucz', 'Wymuszone_Lv1', 'Wymuszone_Lv2', 'Wymuszony_Unit'])
        df_rules.to_excel(rules_path, index=False)
        df_rules = pd.DataFrame(columns=['Slowo_Klucz', 'Wymuszone_Lv1', 'Wymuszone_Lv2', 'Wymuszony_Unit'])
    else:
        df_rules = pd.read_excel(rules_path)
        
    if not os.path.exists(unit_rules_path):
        df_units = pd.DataFrame({'Unit': DEFAULT_UNITS, 'Slowo_Klucz': [''] * len(DEFAULT_UNITS)})
        df_units.to_excel(unit_rules_path, index=False)
    else:
        df_units = pd.read_excel(unit_rules_path)
        if df_units.empty or 'Unit' not in df_units.columns:
             df_units = pd.DataFrame({'Unit': DEFAULT_UNITS, 'Slowo_Klucz': [''] * len(DEFAULT_UNITS)})
             df_units.to_excel(unit_rules_path, index=False)
        
    nlp_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return ontology, nlp_model, df_rules, df_units

def prepare_knowledge_base(models_data, df_dw, type_col, selected_types):
    mask = df_dw[type_col].isin(selected_types)
    ontology, nlp_model, df_rules, df_units = models_data
    
    categories = ontology['Ontologia']['Kategorie']
    docs = []
    lv1_labels = []
    lv2_labels = []
    
    for key, val in categories.items():
        words = val.get('lematy', []) + val.get('kluczowe_tokeny_lv2', [])
        docs.append(" ".join(words))
        lv1_labels.append(val['Lv1'])
        lv2_labels.append(val['Lv2'])
        
    ontology_embeddings = nlp_model.encode(docs, convert_to_tensor=True)
    
    unique_units = list(set(df_units['Unit'].dropna().tolist() + DEFAULT_UNITS))
    unit_embeddings = nlp_model.encode(unique_units, convert_to_tensor=True) if unique_units else None
    
    trained_model = (nlp_model, ontology_embeddings, lv1_labels, lv2_labels, df_rules, df_units, unique_units, unit_embeddings)
    return mask, trained_model, None, None, None

def categorize_nlp(df_dw, mask, trained_model, ref_lv1, ref_lv2, ref_unit, old_model):
    if not mask.any() or trained_model is None:
        return df_dw, 0.0, 0
        
    nlp_model, ontology_embeddings, lv1_labels, lv2_labels, df_rules, df_units, unique_units, unit_embeddings = trained_model
    
    df_to_process = df_dw[mask].copy()
    processed_texts = df_to_process.apply(isolate_problem_description, axis=1).tolist()
    
    # ---------------- ETAP 1: Kaskada Unitu ----------------
    pred_unit = []
    unit_nlp_indices = []
    
    # 1A: Twarde reguły Unitu
    for i, text in enumerate(processed_texts):
        u_val = ""
        rule_applied = False
        if not df_units.empty:
            for idx, rule in df_units.iterrows():
                keyword = str(rule.get('Slowo_Klucz', '')).lower()
                if keyword and keyword != 'nan' and keyword in text:
                    u_val = str(rule.get('Unit', ''))
                    rule_applied = True
                    break
        
        pred_unit.append(u_val)
        if not rule_applied:
            unit_nlp_indices.append(i)

    # 1B: NLP dla Unitu (Tylko dla tych bez twardej reguły - mega oszczędność czasu)
    if unit_nlp_indices and unit_embeddings is not None:
        texts_for_units = [processed_texts[i] for i in unit_nlp_indices]
        unit_inputs = nlp_model.encode(texts_for_units, convert_to_tensor=True, show_progress_bar=False)
        cosine_scores_units = util.cos_sim(unit_inputs, unit_embeddings)
        
        for idx, original_i in enumerate(unit_nlp_indices):
            row_scores = cosine_scores_units[idx]
            best_idx = torch.argmax(row_scores).item()
            best_score = row_scores[best_idx].item() * 100
            if best_score >= 40.0:
                pred_unit[original_i] = unique_units[best_idx]

    # ---------------- ETAP 2: Kaskada Lv1 / Lv2 ----------------
    pred_lv1 = []
    pred_lv2 = []
    scores = []
    
    # Context Injection (Wstrzyknięcie rozpoznanego Unitu do tekstu)
    enriched_texts = [f"{u} {t}".strip() for u, t in zip(pred_unit, processed_texts)]
    lv_nlp_indices = []
    
    # 2A: Twarde reguły Lv1/Lv2 (szukane w oryginale, by nie psuć logiki słów kluczowych)
    for i, text in enumerate(processed_texts):
        rule_applied = False
        if not df_rules.empty:
            for idx, rule in df_rules.iterrows():
                keyword = str(rule.get('Slowo_Klucz', '')).lower()
                if keyword and keyword != 'nan' and keyword in text:
                    pred_lv1.append(rule.get('Wymuszone_Lv1', ''))
                    pred_lv2.append(rule.get('Wymuszone_Lv2', ''))
                    scores.append(100.0)
                    rule_applied = True
                    
                    forced_unit = str(rule.get('Wymuszony_Unit', ''))
                    if forced_unit and forced_unit != 'nan':
                        pred_unit[i] = forced_unit
                    break
                    
        if not rule_applied:
            pred_lv1.append("")
            pred_lv2.append("")
            scores.append(0.0)
            lv_nlp_indices.append(i)

    # 2B: NLP dla Lv1/Lv2 z wykorzystaniem "Wzbogaconego" Tekstu
    if lv_nlp_indices:
        texts_for_lv = [enriched_texts[i] for i in lv_nlp_indices]
        lv_inputs = nlp_model.encode(texts_for_lv, convert_to_tensor=True, show_progress_bar=False)
        cosine_scores_lv = util.cos_sim(lv_inputs, ontology_embeddings)
        
        for idx, original_i in enumerate(lv_nlp_indices):
            row_scores = cosine_scores_lv[idx]
            best_idx = torch.argmax(row_scores).item()
            best_score = row_scores[best_idx].item() * 100
            
            pred_lv1[original_i] = lv1_labels[best_idx]
            pred_lv2[original_i] = lv2_labels[best_idx]
            scores[original_i] = best_score

    # Czyszczenie i zapis wyników do Pandas
    cols_to_clean = ['AI Trouble Keyword Lv1', 'AI Trouble Keyword Lv2', 'AI Unit', 'Status', 'test 1', 'test 2', 'Match_Score_%']
    for c in cols_to_clean:
        if c in df_dw.columns:
            df_dw = df_dw.loc[:, ~df_dw.columns.duplicated()].copy()

    new_cols = ['AI Trouble Keyword Lv1', 'AI Trouble Keyword Lv2', 'AI Unit', 'Status']
    for col in new_cols:
        df_dw[col] = df_dw.get(col, pd.Series(dtype='object')).astype('object')
        
    df_dw['Match_Score_%'] = df_dw.get('Match_Score_%', pd.Series(dtype='float64')).astype('float64')

    df_dw.loc[mask, 'AI Trouble Keyword Lv1'] = pred_lv1
    df_dw.loc[mask, 'AI Trouble Keyword Lv2'] = pred_lv2
    df_dw.loc[mask, 'AI Unit'] = pred_unit
    df_dw.loc[mask, 'Match_Score_%'] = np.round(scores, 2)
    
    conditions = [mask & (df_dw['Match_Score_%'] >= 65), mask & (df_dw['Match_Score_%'] < 65)]
    choices = ['AI: Pewne', 'AI: Do sprawdzenia']
    df_dw['Status'] = np.select(conditions, choices, default=df_dw['Status'])

    mean_score = float(df_dw.loc[mask, 'Match_Score_%'].mean())
    confident_count = int((df_dw.loc[mask, 'Match_Score_%'] >= 65).sum())

    return df_dw, mean_score, confident_count

def update_ai_dictionary(ontology, df_dw):
    return ontology