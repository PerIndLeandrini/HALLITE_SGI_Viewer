import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
from PIL import Image
import io
import os

st.set_page_config(page_title="SGI Viewer", page_icon="📁", layout="wide")

# =========================
# LOGIN MANUALE
# =========================
auth_cfg = st.secrets["auth"]
users_cfg = auth_cfg["credentials"]["usernames"]

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.name = None

if not st.session_state.logged_in:
    st.title("SGI Viewer")
    with st.form("login_form"):
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Accedi")

    if submitted:
        if username_input in users_cfg and password_input == users_cfg[username_input]["password"]:
            st.session_state.logged_in = True
            st.session_state.username = username_input
            st.session_state.name = users_cfg[username_input].get("name", username_input)
            st.rerun()
        else:
            st.error("Credenziali non corrette.")
    st.stop()

# =========================
# SIDEBAR
# =========================
st.sidebar.write(f"👤 {st.session_state.name}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.name = None
    st.rerun()

st.sidebar.markdown("### SGI Viewer")
st.sidebar.markdown("---")

# =========================
# SCELTA CLIENTE
# =========================
folders_cfg = st.secrets["folders"]
user_folders = st.secrets.get("user_folders", {})

username = st.session_state.username

if username in user_folders:
    cliente_scelto = user_folders[username]
    ROOT_FOLDER_ID = folders_cfg[cliente_scelto]
    st.sidebar.markdown(f"📁 Cliente: **{cliente_scelto}**")
else:
    clienti = list(folders_cfg.keys())
    cliente_scelto = st.sidebar.selectbox("Cliente", clienti)
    ROOT_FOLDER_ID = folders_cfg[cliente_scelto]

# --- LOGO DINAMICO PER CLIENTE ---
logo_dir = "LOGHI"
logo_name = f"logo_{cliente_scelto}.png".replace(" ", "_").lower()
logo_path = os.path.join(logo_dir, logo_name)

try:
    logo = Image.open(logo_path)
    st.sidebar.image(logo, use_container_width=True)
except FileNotFoundError:
    # fallback al logo generico
    try:
        logo = Image.open(os.path.join(logo_dir, "logo.png"))
        st.sidebar.image(logo, use_container_width=True)
    except FileNotFoundError:
        st.sidebar.warning("Logo non trovato")
# =========================
# GOOGLE DRIVE
# =========================
from google.oauth2 import service_account as g_service_account

google_info = st.secrets["google"]
creds = g_service_account.Credentials.from_service_account_info(
    google_info,
    scopes=["https://www.googleapis.com/auth/drive.readonly"],
)
drive_service = build("drive", "v3", credentials=creds)

sezione = st.sidebar.radio(
    "Sezione",
    [
        "Documenti di vertice",
        "DVR",
        "Procedure",
        "Moduli",
        "Audit",
        "Risk Managment",
        "Altre cartelle",
    ],
)

search = st.text_input("Cerca documento")

def list_files_in_folder(folder_id: str):
    q = f"'{folder_id}' in parents and trashed = false"
    res = drive_service.files().list(
        q=q,
        pageSize=200,
        fields="files(id, name, mimeType, webViewLink, webContentLink)",
    ).execute()
    return res.get("files", [])

def find_subfolder_id(parent_id: str, subfolder_name: str):
    q = (
        f"'{parent_id}' in parents and "
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"name = '{subfolder_name}' and trashed = false"
    )
    res = drive_service.files().list(
        q=q,
        pageSize=10,
        fields="files(id, name)",
    ).execute()
    items = res.get("files", [])
    return items[0]["id"] if items else None

def show_drive_preview(file_id: str, height: int = 700):
    iframe = (
        f'<iframe src="https://drive.google.com/file/d/{file_id}/preview" '
        f'width="100%" height="{height}" allow="autoplay"></iframe>'
    )
    st.markdown(iframe, unsafe_allow_html=True)

# =========================
# SEZIONI
# =========================
if sezione == "Documenti di vertice":
    st.subheader(f"Documenti di vertice . {cliente_scelto}")
    q = (
        f"'{ROOT_FOLDER_ID}' in parents and trashed = false "
        "and mimeType != 'application/vnd.google-apps.folder'"
    )
    if search:
        q += f" and name contains '{search}'"
    res = drive_service.files().list(
        q=q,
        pageSize=200,
        fields="files(id, name, mimeType, webViewLink, webContentLink)",
    ).execute()
    files = res.get("files", [])

elif sezione == "DVR":
    st.subheader(f"DVR . {cliente_scelto}")
    dvr_id = find_subfolder_id(ROOT_FOLDER_ID, "DVR")
    if not dvr_id:
        st.error("Cartella 'DVR' non trovata.")
        files = []
    else:
        files = [
            f
            for f in list_files_in_folder(dvr_id)
            if f["mimeType"] != "application/vnd.google-apps.folder"
        ]
        if search:
            files = [f for f in files if search.lower() in f["name"].lower()]

elif sezione == "Procedure":
    st.subheader(f"Procedure . {cliente_scelto}")
    proc_id = find_subfolder_id(ROOT_FOLDER_ID, "Procedure")
    if not proc_id:
        st.error("Cartella 'Procedure' non trovata.")
        files = []
    else:
        files = [
            f
            for f in list_files_in_folder(proc_id)
            if f["mimeType"] != "application/vnd.google-apps.folder"
        ]
        if search:
            files = [f for f in files if search.lower() in f["name"].lower()]

elif sezione == "Moduli":
    st.subheader(f"Moduli delle procedure . {cliente_scelto}")
    proc_id = find_subfolder_id(ROOT_FOLDER_ID, "Procedure")
    if not proc_id:
        st.error("Cartella 'Procedure' non trovata.")
        files = []
    else:
        mod_id = find_subfolder_id(proc_id, "Moduli")
        if not mod_id:
            st.error("Cartella 'Moduli' non trovata dentro 'Procedure'.")
            files = []
        else:
            files = [
                f
                for f in list_files_in_folder(mod_id)
                if f["mimeType"] != "application/vnd.google-apps.folder"
            ]
            if search:
                files = [f for f in files if search.lower() in f["name"].lower()]

elif sezione == "Audit":
    st.subheader(f"Audit . {cliente_scelto}")
    audit_id = find_subfolder_id(ROOT_FOLDER_ID, "Audit")
    if not audit_id:
        st.error("Cartella 'Audit' non trovata.")
        files = []
    else:
        files = [
            f
            for f in list_files_in_folder(audit_id)
            if f["mimeType"] != "application/vnd.google-apps.folder"
        ]
        if search:
            files = [f for f in files if search.lower() in f["name"].lower()]

elif sezione == "Risk Managment":
    st.subheader(f"Risk Managment . {cliente_scelto}")
    risk_id = find_subfolder_id(ROOT_FOLDER_ID, "Risk Managment")
    if not risk_id:
        st.error("Cartella 'Risk Managment' non trovata.")
        files = []
    else:
        files = [
            f
            for f in list_files_in_folder(risk_id)
            if f["mimeType"] != "application/vnd.google-apps.folder"
        ]
        if search:
            files = [f for f in files if search.lower() in f["name"].lower()]

else:
    st.subheader(f"Altre cartelle . {cliente_scelto}")
    root_items = list_files_in_folder(ROOT_FOLDER_ID)
    root_folders = [
        i for i in root_items if i["mimeType"] == "application/vnd.google-apps.folder"
    ]
    # escludo quelle già gestite sopra
    esclusi = {
        "Documenti di vertice",
        "DVR",
        "Procedure",
        "Moduli",
        "Audit",
        "Risk Managment",
    }
    root_folders = [f for f in root_folders if f["name"] not in esclusi]

    if not root_folders:
        st.info("Nessun’altra cartella trovata.")
        files = []
    else:
        cartella_scelta = st.selectbox(
            "Seleziona la cartella",
            [f["name"] for f in root_folders],
        )
        folder_id = next(f["id"] for f in root_folders if f["name"] == cartella_scelta)

        items = list_files_in_folder(folder_id)
        subfolders = [
            i
            for i in items
            if i["mimeType"] == "application/vnd.google-apps.folder"
        ]
        files = [
            i
            for i in items
            if i["mimeType"] != "application/vnd.google-apps.folder"
        ]

        if subfolders:
            st.markdown("**Sottocartelle**")
            sotto_nomi = [s["name"] for s in subfolders]
            sotto_sel = st.selectbox(
                "Seleziona una sottocartella (opzionale)", ["(nessuna)"] + sotto_nomi
            )
            if sotto_sel != "(nessuna)":
                sotto_id = next(
                    s["id"] for s in subfolders if s["name"] == sotto_sel
                )
                files = [
                    f
                    for f in list_files_in_folder(sotto_id)
                    if f["mimeType"] != "application/vnd.google-apps.folder"
                ]

        if search:
            files = [f for f in files if search.lower() in f["name"].lower()]

# =========================
# ANTEPRIMA
# =========================
if not files:
    st.info("Nessun documento trovato.")
else:
    names = [f["name"] for f in files]
    selected_name = st.selectbox("Seleziona un documento", names)
    selected_item = next(f for f in files if f["name"] == selected_name)
    file_id = selected_item["id"]
    mime = selected_item["mimeType"]
    webview = selected_item.get("webViewLink")
    webcontent = selected_item.get("webContentLink")

    if st.button("Apri anteprima", key="preview_btn"):
        if mime.startswith("image/"):
            req = drive_service.files().get_media(fileId=file_id)
            img_bytes = io.BytesIO(req.execute())
            st.image(img_bytes, use_container_width=True)
            if webcontent:
                st.markdown(f"[Scarica immagine]({webcontent})")
        else:
            if webview:
                show_drive_preview(file_id)
                if webcontent:
                    st.markdown(f"[Scarica file]({webcontent})")
            else:
                st.warning("Nessun link di anteprima disponibile. usa Drive.")
                if webcontent:
                    st.markdown(f"[Scarica file]({webcontent})")
