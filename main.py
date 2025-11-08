import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
from PIL import Image
import streamlit_authenticator as stauth
import io

st.set_page_config(page_title="SGI Viewer", page_icon="📁", layout="wide")

# ----- LOGIN (da secrets) -----
auth_cfg = st.secrets["auth"]

# secrets è read-only. lo copiamo
credentials = {"usernames": {}}
for uname, data in auth_cfg["credentials"]["usernames"].items():
    credentials["usernames"][uname] = dict(data)

authenticator = stauth.Authenticate(
    credentials,
    auth_cfg["cookie_name"],
    auth_cfg["cookie_key"],
    auth_cfg["cookie_expiry_days"],
)

login_fields = {
    "Form name": "Login",
    "Username": "Username",
    "Password": "Password",
    "Login": "Accedi",
}

# una sola chiamata. prima provo con la firma nuova, se no uso la vecchia
try:
    name, auth_status, username = authenticator.login(
        fields=login_fields,
        location="main",
    )
except TypeError:
    # firma vecchia
    name, auth_status, username = authenticator.login(
        "Login",
        "main",
    )

if auth_status is False:
    st.error("Credenziali non corrette.")
elif auth_status is None:
    st.warning("Inserisci username e password.")
else:
    # ----- SIDEBAR -----
    try:
        logo = Image.open("logo.png")
        st.sidebar.image(logo, use_container_width=True)
    except FileNotFoundError:
        st.sidebar.warning("Logo non trovato (logo.png)")

    st.sidebar.markdown("### SGI Viewer")
    authenticator.logout("Logout", "sidebar")
    st.sidebar.markdown("---")

    # ----- GOOGLE DRIVE -----
    from google.oauth2 import service_account as g_service_account

    google_info = st.secrets["google"]
    creds = g_service_account.Credentials.from_service_account_info(
        google_info,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    drive_service = build("drive", "v3", credentials=creds)

    ROOT_FOLDER_ID = "10TaZC51gHSv3szzz_Kbd_8MF0zuN_5n6"

    sezione = st.sidebar.radio(
        "Sezione",
        [
            "Documenti di vertice",
            "Procedure operative",
            "Moduli procedure",
            "Altre cartelle",
        ],
    )

    search = st.text_input("Cerca documento")

    # ----- FUNZIONI -----
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
        iframe = f'<iframe src="https://drive.google.com/file/d/{file_id}/preview" width="100%" height="{height}" allow="autoplay"></iframe>'
        st.markdown(iframe, unsafe_allow_html=True)

    # ---------- SEZIONI ----------
    if sezione == "Documenti di vertice":
        st.subheader("Documenti di vertice")
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

    elif sezione == "Procedure operative":
        st.subheader("Procedure operative")
        proc_id = find_subfolder_id(ROOT_FOLDER_ID, "PROCEDURE OPERATIVE")
        if not proc_id:
            st.error("Cartella 'PROCEDURE OPERATIVE' non trovata.")
            files = []
        else:
            files = [
                f
                for f in list_files_in_folder(proc_id)
                if f["mimeType"] != "application/vnd.google-apps.folder"
            ]
            if search:
                files = [f for f in files if search.lower() in f["name"].lower()]

    elif sezione == "Moduli procedure":
        st.subheader("Moduli delle procedure")
        proc_id = find_subfolder_id(ROOT_FOLDER_ID, "PROCEDURE OPERATIVE")
        if not proc_id:
            st.error("Cartella 'PROCEDURE OPERATIVE' non trovata.")
            files = []
        else:
            mod_id = find_subfolder_id(proc_id, "MOD")
            if not mod_id:
                st.error("Cartella 'MOD' non trovata dentro 'PROCEDURE OPERATIVE'.")
                files = []
            else:
                files = [
                    f
                    for f in list_files_in_folder(mod_id)
                    if f["mimeType"] != "application/vnd.google-apps.folder"
                ]
                if search:
                    files = [
                        f for f in files if search.lower() in f["name"].lower()
                    ]

    else:
        st.subheader("Altre cartelle")
        root_items = list_files_in_folder(ROOT_FOLDER_ID)
        root_folders = [
            i
            for i in root_items
            if i["mimeType"] == "application/vnd.google-apps.folder"
        ]
        esclusi = {"PROCEDURE OPERATIVE", "MOD"}
        root_folders = [f for f in root_folders if f["name"] not in esclusi]

        if not root_folders:
            st.info("Nessuna altra cartella trovata.")
            files = []
        else:
            cartella_scelta = st.selectbox(
                "Seleziona la cartella",
                [f["name"] for f in root_folders],
            )
            folder_id = next(
                f["id"] for f in root_folders if f["name"] == cartella_scelta
            )

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
                        if f["mimeType"]
                        != "application/vnd.google-apps.folder"
                    ]

            if search:
                files = [f for f in files if search.lower() in f["name"].lower()]

    # ---------- UI PRINCIPALE ----------
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
