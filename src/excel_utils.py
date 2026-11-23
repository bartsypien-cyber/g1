import io
import pandas as pd
import json

def generate_g1_export(df_dw):
    df_export = df_dw.copy()
    
    # KROK 1: Kolumna 'test 1'
    if 'Trouble Keyword Lv1' in df_export.columns and 'AI Trouble Keyword Lv1' in df_export.columns:
        human_lv1 = df_export['Trouble Keyword Lv1'].astype(str).str.strip().str.lower()
        ai_lv1 = df_export['AI Trouble Keyword Lv1'].astype(str).str.strip().str.lower()
        
        df_export['test 1'] = (human_lv1 == ai_lv1).astype(bool)
        
        # Jeśli pole puste - przypisujemy FALSE
        empty_mask = df_export['Trouble Keyword Lv1'].isna() | (human_lv1 == '') | (human_lv1 == 'nan') | (human_lv1 == '[brak przypisania]')
        df_export.loc[empty_mask, 'test 1'] = False

    # KROK 2: Kolumna 'test 2'
    if 'Trouble Keyword Lv2' in df_export.columns and 'AI Trouble Keyword Lv2' in df_export.columns:
        human_lv2 = df_export['Trouble Keyword Lv2'].astype(str).str.strip().str.lower()
        ai_lv2 = df_export['AI Trouble Keyword Lv2'].astype(str).str.strip().str.lower()
        
        df_export['test 2'] = (human_lv2 == ai_lv2).astype(bool)
        
        # Jeśli pole puste - przypisujemy FALSE
        empty_mask_2 = df_export['Trouble Keyword Lv2'].isna() | (human_lv2 == '') | (human_lv2 == 'nan') | (human_lv2 == '[brak przypisania]')
        df_export.loc[empty_mask_2, 'test 2'] = False

    # KROK 3: Wycięcie zbędnych kolumn i wymuszenie docelowej kolejności
    essential_cols = [
        'Loss Name', 'Trouble Keyword Lv1', 'Trouble Keyword Lv2', 
        'AI Trouble Keyword Lv1', 'AI Trouble Keyword Lv2', 'AI Unit',
        'test 1', 'test 2', 'Match_Score_%', 'Status',
        'Detailed Loss Name', 'Loss Note', 'Remark', 
        'Date of Work', 'Start Time of Occurrence', 'End Time of Occurrence', 
        'Time of Occurrence (Sec)', 'Line Name', 'Unit', 'real time'
    ]
    
    final_cols = [c for c in essential_cols if c in df_export.columns]
    df_export = df_export[final_cols]
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Do_Wklejenia')
        
    return output.getvalue()

def generate_dict_export(ontology_dict):
    if ontology_dict is None:
        ontology_dict = {}
    json_string = json.dumps(ontology_dict, indent=4, ensure_ascii=False)
    return json_string.encode('utf-8')