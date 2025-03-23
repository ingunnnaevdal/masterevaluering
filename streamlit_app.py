import streamlit as st
import pandas as pd
import random
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os
import ast

st.set_page_config(layout="wide")

load_dotenv()
password = os.getenv("MONGODB_PASSWORD")
uri = f"mongodb+srv://ingunn:{password}@samiaeval.2obnm.mongodb.net/?retryWrites=true&w=majority&tlsAllowInvalidCertificates=true"

client = MongoClient(uri, server_api=ServerApi('1'))
evaluering_kolleksjon = client['SamiaEvalDB']['personalisering_VOL3']


def les_datasett(filsti):
    try:
        return pd.read_csv(filsti)
    except FileNotFoundError:
        st.error(f"Filen {filsti} ble ikke funnet.")
        st.stop()
    except pd.errors.ParserError:
        st.error(f"Kunne ikke lese filen {filsti}. Sjekk formatet.")
        st.stop()


def lagre_evaluering_mongodb(kolleksjon, evaluering):
    try:
        kolleksjon.insert_one(evaluering)
        st.success("Evaluering lagret!")
    except Exception as e:
        st.error(f"Feil under lagring i MongoDB: {e}")


def vis_tekst_sammendrag(tekst):
    try:
        tekst = ast.literal_eval(tekst) 
    except (SyntaxError, ValueError):
        pass

    if isinstance(tekst, list):
        tekst = [punkt.replace("•", "").strip() for punkt in tekst]
        tekst = [f"- {punkt}" if not punkt.startswith("-") else punkt for punkt in tekst]
        st.markdown("\n".join(tekst), unsafe_allow_html=True)
    else:
        st.write(tekst)


bruker_id = st.text_input("Skriv inn ditt navn eller ID:", key="bruker_id")
if not bruker_id:
    st.stop()

undersokelse_svart = evaluering_kolleksjon.find_one({'bruker_id': bruker_id, 'type': 'undersokelse'})

if not undersokelse_svart:
    st.title("Brukerundersøkelse")
    st.header("Før vi starter, vennligst svar på noen spørsmål:")

    svar_lengde = st.radio(
        "Hvor lange mener du at nyhetssammendrag burde være?",
        options=["1-2 setninger", "Et kort avsnitt", "En mer detaljert oppsummering (flere avsnitt)", "Varierer avhengig av sakens kompleksitet"]
    )

    svar_presentasjon = st.radio(
        "Hvordan foretrekker du at nyhetssammendrag presenteres?",
        options=[
            "Nøytralt og objektivt, uten vurderinger",
            "Kort og konsist, med kun de viktigste fakta",
            "Med en kort vurdering av saken",
            "Med forklaringer av komplekse begreper eller sammenhenger"
        ]
    )

    svar_bakgrunn = st.radio(
        "Hvor viktig er det at nyhetssammendrag gir bakgrunnsinformasjon og kontekst?",
        options=["Svært viktig", "Litt viktig", "Ikke viktig"]
    )

    svar_viktigst = st.radio(
        "Hva er viktigst for deg?",
        options=[
            "At nyhetssammendraget gir meg all relevant informasjon raskt",
            "At nyhetssammendraget forklarer hvorfor saken er viktig",
            "At nyhetssammendraget er enkelt å forstå",
            "At nyhetssammendraget har god språklig kvalitet"
        ]
    )

    svar_irriterende = st.radio(
        "Hva ville irritert deg mest med et nyhetssammendrag?",
        options=[
            "Upresis eller unøyaktig informasjon",
            "For mye tekst eller unødvendige detaljer",
            "Mangel på kontekst eller bakgrunn",
            "Et subjektivt eller vinklet språk"
        ]
    )

    if st.button("Start evaluering"):
        undersokelse = {
            'bruker_id': bruker_id,
            'type': 'undersokelse',
            'svar_lengde': svar_lengde,
            'svar_presentasjon': svar_presentasjon,
            'svar_bakgrunn': svar_bakgrunn,
            'svar_viktigst': svar_viktigst,
            'svar_irriterende': svar_irriterende
        }
        evaluering_kolleksjon.insert_one(undersokelse)
        st.success("Takk for at du svarte! Du kan nå starte evalueringen.")
        st.rerun()
else:
    st.write("Takk for at du svarte på undersøkelsen tidligere! Du kan nå fortsette til evalueringen.")


filsti = 'data.csv'
data = les_datasett(filsti)

user_config = evaluering_kolleksjon.find_one({
    'bruker_id': bruker_id,
    'type': 'user_config'
})

if not user_config:
    random_order = list(range(len(data)))
    random.shuffle(random_order)

    p = set(range(1, min(len(data), 6)))  

    if len(random_order) > 1 and len(p) > 0:
        first_two = random_order[:2]
        if not any(idx in p for idx in first_two):
            for j in range(2, len(random_order)):
                if random_order[j] in p:
                    random_order[1], random_order[j] = random_order[j], random_order[1]
                    break

    user_config = {
        'bruker_id': bruker_id,
        'type': 'user_config',
        'random_order': random_order,
        'current_index': 0
    }
    evaluering_kolleksjon.insert_one(user_config)
else:
    random_order = user_config['random_order']

current_index = user_config['current_index']

if current_index >= len(random_order):
    st.success("Alle artikler er evaluert!")
    st.stop()

this_article_idx = random_order[current_index]
row = data.iloc[this_article_idx]

st.header(f"Artikkel {current_index + 1}/{len(data)}")
st.markdown(f"""
<div class='main-container'>
    <h1 class='article-title'>{row['title']}</h1>
    <div class='lead-text'>{row['byline']}</div>
    <div class='lead-text'>Publisert: {row['creation_date']}</div>
    <div class='lead-text'>{row['lead_text']}</div>
    <div class='article-body'>{row['artikkeltekst']}</div>
</div>
""", unsafe_allow_html=True)

if f"valgte_sammendrag_{bruker_id}_{current_index}" not in st.session_state:
    all_prompt_cols = [col for col in row.index if 'prompt' in col and pd.notna(row[col])]

    prompt4_cols = [col for col in all_prompt_cols if 'prompt4' in col]
    other_prompt_cols = list(set(all_prompt_cols) - set(prompt4_cols))

    random.shuffle(prompt4_cols)
    random.shuffle(other_prompt_cols)

    selected_cols = []
    if len(prompt4_cols) >= 2:
        selected_cols.extend(prompt4_cols[:2])
        needed = 4 - len(selected_cols)
        if len(other_prompt_cols) >= needed:
            selected_cols.extend(other_prompt_cols[:needed])
        else:
            selected_cols.extend(prompt4_cols[2:2 + needed])
    else:
        random.shuffle(all_prompt_cols)
        selected_cols = all_prompt_cols[:4]

    sammendrag_liste = [(col.replace('prompt_', ''), row[col]) for col in selected_cols]
    random.shuffle(sammendrag_liste)

    st.session_state[f"valgte_sammendrag_{bruker_id}_{current_index}"] = sammendrag_liste

valgte_sammendrag = st.session_state[f"valgte_sammendrag_{bruker_id}_{current_index}"]

st.subheader("Sammendrag:")
rankings = {}
ranking_options = ["Best", "Nest best", "Nest dårligst", "Dårligst"]

for i, (kilde, tekst) in enumerate(valgte_sammendrag):
    with st.expander(f"Sammendrag {i + 1}"):
        vis_tekst_sammendrag(tekst)
        rankings[kilde] = st.selectbox(
            f"Ranger sammendrag {i + 1}",
            ranking_options,
            key=f"ranking_{bruker_id}_{current_index}_{i}"
        )

kommentar = st.text_area("Kommentar:", key=f"kommentar_{bruker_id}_{current_index}")

if st.button("Lagre evaluering", key=f"lagre_{bruker_id}_{current_index}"):
    evaluering = {
        'bruker_id': bruker_id,
        'type': 'artikkel_evaluering',
        'random_list_pos': current_index,
        'data_idx': this_article_idx,
        'uuid': row['uuid'],
        'rangeringer': rankings,
        'sammendrag_kilder': [kilde for kilde, _ in valgte_sammendrag],
        'kommentar': kommentar
    }
    lagre_evaluering_mongodb(evaluering_kolleksjon, evaluering)

    current_index += 1
    evaluering_kolleksjon.update_one(
        {'_id': user_config['_id']},
        {'$set': {'current_index': current_index}}
    )

    st.rerun()

st.markdown("""
    <style>
        .main-container {
            max-width: 800px;  /* Gjør containeren smalere */
            margin: auto;
            padding: 20px;
            background-color: #f9f9f9;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            max-height: 800px;  /* Begrens høyden */
            overflow-y: auto;   /* Legg til vertikal scroll */
        }
        .article-title {
            font-size: 28px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }
        .lead-text {
            font-size: 18px;
            color: #555;
            margin-bottom: 20px;
        }
        .article-body {
            font-size: 16px;
            line-height: 1.6;
            color: #444;
            margin-bottom: 30px;
        }
        .summary-box {
            background: white;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        .summary-header {
            font-weight: bold;
            margin-bottom: 10px;
        }
        .evaluation-section {
            background-color: #fff;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
        }
        .evaluation-button {
            background-color: #2051b3;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }
        .evaluation-button:hover {
            background-color: #183c85;
        }
    </style>
""", unsafe_allow_html=True)
