import streamlit as st
import requests
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import random
import threading
import concurrent.futures
import extra_streamlit_components as stx
import urllib.parse

# 구글 인증 관련 라이브러리
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport.requests import Request as GoogleRequest

# 1. 사이트 기본 설정
st.set_page_config(page_title="애니 아카이브", page_icon="🎬", layout="wide")

# --- 쿠키 매니저 설정 (고유 키 추가) ---
# --- 쿠키 매니저 설정 및 데이터 로드 (최상단 통합) ---
cookie_manager = stx.CookieManager(key="anime_cookie_manager")
all_cookies = cookie_manager.get_all()

# --- UI 레이아웃 및 디자인 고정 CSS ---
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }
    .stImage > img, [data-testid="stImage"] img {
        width: 100% !important; height: 500px !important; 
        object-fit: cover !important; border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .anime-title-box {
        margin-top: 15px !important; height: 3.5rem !important; 
        line-height: 1.75rem !important; font-size: 1.1rem;
        font-weight: 700; overflow: hidden; display: -webkit-box;
        -webkit-line-clamp: 2; -webkit-box-orient: vertical;
        color: var(--text-color);
    }
    .anime-info-box {
        font-size: 0.85rem; color: var(--secondary-text-color); margin-top: 4px;
        height: 1.2rem; line-height: 1.2rem;
    }
    .score-box {
        margin-top: 5px !important; margin-bottom: 12px !important;
        font-size: 0.95rem; color: #f39c12; font-weight: 700;
        display: flex; align-items: center; gap: 4px;
        height: 1.5rem;
    }
    .user-comment-box {
        background-color: rgba(128, 128, 128, 0.1); border-left: 3px solid #4CAF50;
        padding: 8px; border-radius: 4px; margin-bottom: 10px;
        font-size: 0.85rem; color: var(--text-color);
        height: 65px; overflow-y: auto;
        box-sizing: border-box;
        white-space: pre-line;
    }
    .empty-comment-box {
        height: 65px; margin-bottom: 10px;
        box-sizing: border-box;
    }
    .anime-card-container {
        max-width: 320px;
        margin: 0 auto;
    }
    .watched-badge {
        background-color: #4CAF50;
        color: white;
        padding: 0 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        height: 1.5rem;      /* 높이 고정 */
        line-height: 1.5rem; /* 텍스트 수직 중앙 정렬 */
        margin-bottom: 4px;
        box-sizing: border-box;
    }
    .wish-badge {
        background-color: #f39c12;
        color: white;
        padding: 0 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        height: 1.5rem;
        line-height: 1.5rem;
        margin-bottom: 4px;
        box-sizing: border-box;
    }
    .dropped-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 0 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        height: 1.5rem;
        line-height: 1.5rem;
        margin-bottom: 4px;
        box-sizing: border-box;
    }
    .google-login-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background-color: white;
        color: rgb(49, 51, 63) !important;
        padding: 0.25rem 0.75rem;
        border-radius: 0.5rem;
        text-decoration: none;
        border: 1px solid rgba(49, 51, 63, 0.2);
        width: 100%;
        height: 38.4px;
        font-size: 1rem;
        transition: border-color 0.2s, color 0.2s;
        margin-top: 10px;
    }
    .google-login-btn:hover {
        border-color: rgb(255, 75, 75);
        color: rgb(255, 75, 75) !important;
    }

    /* 1. 사이드바의 모든 멀티셀렉트 태그 기본 설정 (파란색) */
    [data-testid="stSidebar"] [data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        background-color: #2e67ff !important;
    }
    
    /* 2. '제외 장르'는 '포함 장르' 바로 다음에 오는 멀티셀렉트이므로, 인접 형제 선택자(+) 활용 */
    /* element-container들 사이의 관계를 이용하여 두 번째 멀티셀렉트만 빨간색으로 변경 */
    [data-testid="stSidebar"] div:has(>[data-testid="stMultiSelect"]) + div:has(>[data-testid="stMultiSelect"]) span[data-baseweb="tag"] {
        background-color: #ff4b4b !important;
    }

    /* 태그 내부 글자 및 아이콘 공통 설정 (흰색) */
    span[data-baseweb="tag"] span, span[data-baseweb="tag"] div {
        color: white !important;
    }
    span[data-baseweb="tag"] div:hover {
        background-color: rgba(255, 255, 255, 0.2) !important;
    }
    .relation-item {
        display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
        padding: 5px; border-radius: 8px; background: rgba(128, 128, 128, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.1);
    }
    .relation-type {
        font-size: 0.7rem; color: #fff; background: #666;
        padding: 2px 6px; border-radius: 4px; min-width: 60px; text-align: center;
    }
    .relation-title {
        font-size: 0.85rem; font-weight: 600; white-space: nowrap;
        overflow: hidden; text-overflow: ellipsis; flex-grow: 1;
    }
    /* 팝오버 너비 고정 및 장르 줄바꿈 설정 */
    div[data-testid="stPopoverBody"] {
        max-width: 280px !important;
        min-width: 240px !important;
    }
    div[data-testid="stPopoverBody"] .stMarkdown {
        word-break: normal !important;
        white-space: normal !important;
    }
    .genre-tag {
        display: inline-block;
        background-color: rgba(128, 128, 128, 0.1);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 0 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
        height: 1.4rem;
        line-height: 1.4rem;
        margin-right: 4px;
        margin-bottom: 4px;
        white-space: nowrap;
        color: inherit !important;
        text-decoration: none !important;
        transition: all 0.2s;
    }
    .genre-tag:hover {
        background-color: rgba(255, 75, 75, 0.1) !important;
        border-color: rgba(255, 75, 75, 0.3) !important;
        color: #ff4b4b !important;
        cursor: pointer !important;
    }
    /* 상세 팝오버 내 장르 버튼(컬럼 내부) 크기 축소 및 줄바꿈 방지 */
    div[data-testid="stPopoverBody"] [data-testid="stHorizontalBlock"] button {
        padding: 0px 2px !important;
        min-height: 1.7rem !important;
        height: 1.7rem !important;
        font-size: 0.7rem !important;
        line-height: 1 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
    }
    div[data-testid="stPopoverBody"] [data-testid="column"] {
        padding: 1px !important;
    }
    div[data-testid="stPopoverBody"] [data-testid="stHorizontalBlock"] {
        gap: 4px !important;
    }
    div[data-testid="stPopoverBody"] [data-testid="stHorizontalBlock"] button div p {
        white-space: nowrap !important;
        font-size: 0.7rem !important;
    }
    /* 사이드바 내 중첩된 익스팬더(분기별 통계)의 버튼을 링크 스타일로 변경 */
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpander"] button {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        color: #666 !important;
        text-decoration: none !important;
        text-align: left !important;
        font-size: 0.85rem !important;
        font-weight: normal !important;
        display: inline !important;
        width: auto !important;
        height: auto !important;
        min-height: 0 !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpander"] button div p {
        font-size: 0.85rem !important;
        font-weight: normal !important;
        color: inherit !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpander"] button:hover {
        color: #ff4b4b !important;
        text-decoration: none !important;
    }

    /* 분기별 통계 모바일 한 줄 유지 및 세로 중앙 정렬 */
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpander"] [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 8px !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpander"] [data-testid="column"] {
        padding: 0 !important;
        min-width: fit-content !important;
    }
    .q-stat-text {
        white-space: nowrap !important;
        font-size: 0.8rem !important;
        text-align: right !important;
        display: block !important;
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

# 0. 글로벌 인증 저장소 (세션 유실 시에도 서버 메모리에 보존)
@st.cache_resource
def get_oauth_storage():
    return {}

oauth_storage = get_oauth_storage()

# --- 글로벌 상수 ---
KO_GENRE_MAP = {
    "Action": "액션", "Adventure": "모험", "Comedy": "코미디", "Drama": "드라마", "Ecchi": "에치",
    "Fantasy": "판타지", "Horror": "공포", "Mahou Shoujo": "마법소녀", "Mecha": "메카", 
    "Music": "음악", "Mystery": "미스터리", "Psychological": "심리", "Romance": "로맨스", 
    "Sci-Fi": "SF", "Slice of Life": "일상", "Sports": "스포츠", "Supernatural": "초자연", "Thriller": "스릴러"
}

# 기본 플랫폼 프리셋
DEFAULT_PLATFORMS = {
    "LinkKF": "https://linkkf.live/?s={query}",
    "라프텔 (Laftel)": "https://laftel.net/search?keyword={query}",
    "웨이브 (Wavve)": "https://www.wavve.com/search?searchWord={query}",
    "왓챠 (Watcha)": "https://watcha.com/search?query={query}",
    "티빙 (TVING)": "https://www.tving.com/search?keyword={query}",
    "넷플릭스": "https://www.netflix.com/search?q={query}",
    "유튜브 (PV/OST)": "https://www.youtube.com/results?search_query={query}+애니",
    "나무위키": "https://namu.wiki/w/{query}",
    "구글 검색": "https://www.google.com/search?q={query}+애니"
}

# 2. Firebase 초기화 (Secrets 구조 보정)
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            def clean_secrets(obj):
                if hasattr(obj, "to_dict"):
                    return clean_secrets(obj.to_dict())
                if isinstance(obj, dict):
                    return {k: clean_secrets(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [clean_secrets(i) for i in obj]
                return obj

            if "firebase_service_account" in st.secrets:
                sec = clean_secrets(st.secrets["firebase_service_account"])
                
                key_dict = None
                if isinstance(sec, str):
                    key_dict = json.loads(sec, strict=False)
                elif isinstance(sec, dict):
                    inner = sec.get("firebase_service_account")
                    if isinstance(inner, str):
                        key_dict = json.loads(inner, strict=False)
                    elif isinstance(inner, dict):
                        key_dict = inner
                    else:
                        key_dict = sec
                
                if key_dict:
                    cred = credentials.Certificate(key_dict)
                    firebase_admin.initialize_app(cred)
                else:
                    st.error("Firebase 설정을 파싱할 수 없습니다. 형식을 확인해주세요.")
                    return None
            else:
                st.error("설정 오류: secrets.toml 파일에 [firebase_service_account] 섹션이 없습니다.")
                return None
        except Exception as e:
            st.error(f"Firebase 초기화 실패: {e}")
            return None
    return firestore.client()

db = init_firebase()
app_id = "k-anime-archive-v3"

# --- DB 함수 (캐싱 및 구조 최적화) ---
@st.cache_data(ttl=600, show_spinner=False)
def load_user_data_from_db(user_email):
    if not db or not user_email: return {}, {}
    try:
        user_ref = db.collection("artifacts").document(app_id).collection("users").document(user_email)
        doc = user_ref.get()
        
        watched_data = {}
        preferences = {}
        if doc.exists:
            data_dict = doc.to_dict()
            watched_data = data_dict.get("watched", {})
            preferences = data_dict.get("preferences", {})
            if data_dict.get("migrated"):
                return {int(k): v for k, v in watched_data.items()}, preferences
        
        legacy_ref = user_ref.collection("watched")
        legacy_check = list(legacy_ref.limit(1).stream())
        
        if legacy_check:
            legacy_docs = list(legacy_ref.stream())
            new_map = {ldoc.id: ldoc.to_dict() for ldoc in legacy_docs}
            user_ref.set({"watched": new_map, "migrated": True}, merge=True)
            for ldoc in legacy_docs:
                ldoc.reference.delete()
            watched_data = new_map
        else:
            user_ref.set({"migrated": True}, merge=True)
            
        return {int(k): v for k, v in watched_data.items()}, preferences
    except Exception as e:
        err_msg = str(e)
        if "Quota exceeded" in err_msg or "ResourceExhausted" in err_msg or "429" in err_msg:
            st.error("🚨 **데이터베이스 일일 사용 한도를 초과했습니다.**\n\nFirebase 무료 요금제의 일일 읽기 제한(50,000회)에 도달하여 데이터를 가져올 수 없습니다. **내일 오후 4~5시경**에 한도가 리셋되면 정상 이용이 가능합니다. 최적화가 완료되었으므로 리셋 후에는 다시 발생할 확률이 매우 낮습니다.")
            return {}, {}
        raise e

def sync_user_data_to_session(user_email):
    """DB에서 사용자 데이터를 가져와 세션에 동기화합니다."""
    watched, prefs = load_user_data_from_db(user_email)
    st.session_state.watched_list = watched
    if prefs:
        if "time_unit" in prefs:
            st.session_state.time_unit = prefs["time_unit"]
        if "selected_platforms" in prefs:
            st.session_state.selected_platforms = prefs["selected_platforms"]
        if "custom_platforms" in prefs:
            st.session_state.custom_platforms = prefs["custom_platforms"]

def update_db(anime_id, action="add", rating=5.0, comment="", count=1, status="watched"):
    if not db or not st.session_state.get("logged_in"): return
    user_email = st.session_state.user_info.get("email")
    user_ref = db.collection("artifacts").document(app_id).collection("users").document(user_email)
    
    def run_in_thread():
        try:
            if action == "add":
                user_ref.set({
                    "watched": {
                        str(anime_id): {
                            "id": anime_id, 
                            "at": datetime.now(), 
                            "rating": rating,
                            "comment": comment,
                            "count": count,
                            "status": status
                        }
                    }
                }, merge=True)
            else:
                user_ref.update({
                    f"watched.{anime_id}": firestore.DELETE_FIELD
                })
        except Exception: pass

    threading.Thread(target=run_in_thread, daemon=True).start()
    load_user_data_from_db.clear()

def batch_update_db(data_dict):
    if not db or not st.session_state.get("logged_in"): return
    user_email = st.session_state.user_info.get("email")
    user_ref = db.collection("artifacts").document(app_id).collection("users").document(user_email)
    
    def run_in_thread():
        try:
            db_data = {}
            for aid, info in data_dict.items():
                db_data[str(aid)] = {
                    "id": int(aid),
                    "at": datetime.now(),
                    "rating": float(info.get('rating', 5.0)),
                    "comment": str(info.get('comment', "")),
                    "count": int(info.get('count', 1)),
                    "status": info.get('status', 'watched')
                }
            user_ref.set({"watched": db_data}, merge=True)
        except Exception: pass

    threading.Thread(target=run_in_thread, daemon=True).start()
    load_user_data_from_db.clear()

def update_user_setting(key, value):
    if not db or not st.session_state.get("logged_in"): return
    user_email = st.session_state.user_info.get("email")
    user_ref = db.collection("artifacts").document(app_id).collection("users").document(user_email)
    
    def run_in_thread():
        try:
            user_ref.set({"preferences": {key: value}}, merge=True)
        except Exception: pass

    threading.Thread(target=run_in_thread, daemon=True).start()
    load_user_data_from_db.clear()

# --- API 공통 요청 함수 (429 에러 대응 및 재시도 로직) ---
def safe_anilist_request(query, variables, max_retries=3):
    url = 'https://graphql.anilist.co'
    for i in range(max_retries):
        try:
            res = requests.post(url, json={'query': query, 'variables': variables}, timeout=15)
            if res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", 1))
                import time
                time.sleep(retry_after + i)
                continue
            
            if res.status_code == 400:
                try:
                    err_json = res.json()
                    if 'errors' in err_json:
                        return None, f"AniList Error: {err_json['errors'][0].get('message')}"
                except: pass
            
            res.raise_for_status()
            res_json = res.json()
            if 'errors' in res_json:
                return None, res_json['errors']
            return res_json.get('data', {}), None
        except Exception as e:
            if i == max_retries - 1:
                return None, str(e)
            import time
            time.sleep(1 * (i + 1))
    return None, "최대 재시도 횟수를 초과했습니다."

# --- 유틸리티 함수 (Module Level) ---
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_metadata_from_api(missing_ids):
    if not missing_ids: return {}
    
    query = '''
    query ($ids: [Int]) {
      Page(page: 1, perPage: 50) {
        media(id_in: $ids, type: ANIME) {
          id
          title { native romaji }
          episodes
          duration
          genres
          season
          seasonYear
          relations {
            edges {
              relationType(version: 2)
              node { id type }
            }
          }
        }
      }
    }
    '''
    
    def fetch_chunk(chunk):
        chunk_data = {}
        data, errors = safe_anilist_request(query, {'ids': chunk})
        if data:
            for m in data.get('Page', {}).get('media', []):
                chunk_data[int(m['id'])] = {
                    'title': m.get('title', {}),
                    'episodes': m.get('episodes') or 0,
                    'duration': m.get('duration') or 0,
                    'genres': m.get('genres', []),
                    'season': m.get('season'),
                    'seasonYear': m.get('seasonYear'),
                    'relations': m.get('relations', {}).get('edges', [])
                }
        return chunk_data

    results = {}
    chunks = [missing_ids[i:i+50] for i in range(0, len(missing_ids), 50)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_chunk = {executor.submit(fetch_chunk, chunk): chunk for chunk in chunks}
        for future in concurrent.futures.as_completed(future_to_chunk):
            results.update(future.result())
    return results

def get_watched_metadata(ids, p_bar_container=None):
    if not ids: return {}
    if "metadata_storage" not in st.session_state:
        st.session_state.metadata_storage = {}
        
    clean_ids = list(set(int(x) for x in ids))
    missing_ids = [i for i in clean_ids if i not in st.session_state.metadata_storage or 'seasonYear' not in st.session_state.metadata_storage[i]]
    
    if missing_ids:
        chunks = [missing_ids[i:i+50] for i in range(0, len(missing_ids), 50)]
        total_chunks = len(chunks)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_chunk = {executor.submit(fetch_metadata_from_api, tuple(chunk)): chunk for chunk in chunks}
            completed = 0
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    res = future.result()
                    st.session_state.metadata_storage.update(res)
                    completed += 1
                    if p_bar_container:
                        progress = completed / total_chunks
                        p_bar_container.progress(progress, f"분석 중... ({completed}/{total_chunks})")
                except: pass
            
    return {i: st.session_state.metadata_storage[i] for i in clean_ids if i in st.session_state.metadata_storage}

# 3. 구글 OAuth 설정 함수
def get_google_auth_flow():
    try:
        if "google_oauth" not in st.secrets:
            st.error("설정 오류: secrets.toml 파일에 [google_oauth] 섹션이 없습니다.")
            return None
            
        client_config = {
            "web": {
                "client_id": st.secrets["google_oauth"]["client_id"].strip(),
                "client_secret": st.secrets["google_oauth"]["client_secret"].strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [st.secrets["google_oauth"]["redirect_uri"].strip()]
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
        )
        flow.redirect_uri = st.secrets["google_oauth"]["redirect_uri"].strip()
        return flow
    except Exception as e:
        st.error(f"구글 설정 읽기 오류: {e}")
        return None

# 4. 세션 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.session_state.watched_list = None
    st.session_state.auth_checked = False
    st.session_state.logout_clicked = False

if 'all_media' not in st.session_state: st.session_state.all_media = []
if 'random_media' not in st.session_state: st.session_state.random_media = None
if 'is_random_mode' not in st.session_state: st.session_state.is_random_mode = False
if 'page' not in st.session_state: st.session_state.page = 1
if 'api_page' not in st.session_state: st.session_state.api_page = 1
if 'has_next' not in st.session_state: st.session_state.has_next = True
if 'last_filters' not in st.session_state: st.session_state.last_filters = {}
if 'sort_by' not in st.session_state: st.session_state.sort_by = "인기도순"
if 'total_pages' not in st.session_state: st.session_state.total_pages = 1
if 'action_cnt' not in st.session_state: st.session_state.action_cnt = 0
if 'genre_filter' not in st.session_state: st.session_state.genre_filter = []
if 'genre_to_add' not in st.session_state: st.session_state.genre_to_add = None
if 'time_unit' not in st.session_state: st.session_state.time_unit = "시간"
if 'selected_platforms' not in st.session_state: st.session_state.selected_platforms = ["AniLife", "LinkKF"]
if 'custom_platforms' not in st.session_state: st.session_state.custom_platforms = {}

# --- 장르 추가 대기열 처리 ---
if st.session_state.genre_to_add:
    new_g = st.session_state.genre_to_add
    current_g = list(st.session_state.genre_filter)
    if new_g not in current_g:
        current_g.append(new_g)
        st.session_state.genre_filter = current_g
    st.session_state.genre_to_add = None

# --- [앱 보호막: 인증 확인 전까지 UI 차단] ---
def run_auth_shield():
    if st.query_params.get("logout") == "true":
        redundant_params = ["state", "code", "scope", "authuser", "prompt", "iss"]
        changed = False
        for p in redundant_params:
            if p in st.query_params:
                del st.query_params[p]
                changed = True
        if changed:
            st.rerun()
        return False

    if st.session_state.get('logged_in'):
        if "code" in st.query_params or "state" in st.query_params:
            st.query_params.clear()
        return True
    
    auth_code = st.query_params.get("code")
    auth_state = st.query_params.get("state")
    
    if auth_code and auth_state:
        code_verifier = oauth_storage.pop(auth_state, None)
        if code_verifier:
            try:
                flow = get_google_auth_flow()
                if flow:
                    flow.fetch_token(code=auth_code, code_verifier=code_verifier)
                    credentials = flow.credentials
                    id_info = id_token.verify_oauth2_token(
                        credentials.id_token, GoogleRequest(), flow.client_config['client_id']
                    )
                    picture_url = id_info.get("picture")
                    if picture_url and "=s96-c" in picture_url:
                        picture_url = picture_url.replace("=s96-c", "=s500-c")
                    user_info = {"email": id_info.get("email"), "name": id_info.get("name"), "picture": picture_url}
                    
                    st.session_state.user_info = user_info
                    st.session_state.logged_in = True
                    
                    user_key = "anime_user_session"
                    expires = datetime.now() + timedelta(days=30)
                    cookie_manager.set(user_key, user_info, expires_at=expires, key="save_user_cookie")
                    
                    user_info_json = json.dumps(user_info, ensure_ascii=False)
                    encoded_val = urllib.parse.quote(user_info_json)
                    st.components.v1.html(f"""
                        <script>
                            const val = "{encoded_val}";
                            const exp = "{expires.strftime('%a, %d %b %Y %H:%M:%S GMT')}";
                            document.cookie = "{user_key}=" + val + "; path=/; expires=" + exp + "; SameSite=Lax";
                        </script>
                    """, height=0)
                    
                    sync_user_data_to_session(user_info["email"])
                    import time; time.sleep(0.5)
                    st.query_params.clear()
                    st.rerun()
            except Exception: st.query_params.clear()
        else:
            st.query_params.clear()
            st.rerun()
        
    user_key = "anime_user_session"
    if all_cookies is None:
        return False
        
    cookie_val = all_cookies.get(user_key)
    if cookie_val:
        try:
            import base64
            user_info = None
            if isinstance(cookie_val, dict):
                user_info = cookie_val
            else:
                try:
                    decoded = urllib.parse.unquote(cookie_val)
                    user_info = json.loads(decoded)
                except:
                    try:
                        decoded = base64.b64decode(cookie_val).decode('utf-8')
                        user_info = json.loads(decoded)
                    except:
                        user_info = json.loads(cookie_val)
            
            if user_info and isinstance(user_info, dict) and "email" in user_info:
                st.session_state.user_info = user_info
                st.session_state.logged_in = True
                if st.session_state.watched_list is None:
                    sync_user_data_to_session(user_info["email"])
                st.rerun()
        except: pass
    return False

run_auth_shield()

MAX_SAFE_PAGE = 200

# 6. API 호출 (캐싱)
@st.cache_data(ttl=3600)
def fetch_anime(page, sort, year=None, season=None, genres=None, ex_genres=None, search=None, ids=None, exclude_ids=None, include_adult=False, per_page=24, show_error=True):
    if page * per_page > 4800:
        return None
    
    url = 'https://graphql.anilist.co'
    media_fields = "id title { native romaji } coverImage { extraLarge large } averageScore popularity siteUrl season seasonYear trailer { id site } startDate { year month day } format genres"
    
    if isinstance(sort, str):
        sort = [sort]
        
    base_vars = {'p': page, 'sort': sort}
    if year: base_vars['y'] = year
    if season: base_vars['s'] = season
    if genres: base_vars['g'] = genres
    if ex_genres: base_vars['eg'] = ex_genres
    if search: base_vars['q'] = search
    if ids is not None: base_vars['ids'] = ids
    if exclude_ids is not None: base_vars['ex_ids'] = exclude_ids

    def build_query(is_adult_filter):
        return f'''
        query ($y: Int, $s: MediaSeason, $p: Int, $sort: [MediaSort], $g: [String], $eg: [String], $q: String, $ids: [Int], $ex_ids: [Int]) {{
          Page(page: $p, perPage: {per_page}) {{
            pageInfo {{ lastPage hasNextPage }}
            media(id_in: $ids, id_not_in: $ex_ids, search: $q, season: $s, seasonYear: $y, type: ANIME, sort: $sort, genre_in: $g, genre_not_in: $eg, isAdult: {is_adult_filter}) {{
              {media_fields}
            }}
          }}
        }}
        '''

    def make_request(is_adult):
        data, errors = safe_anilist_request(build_query("true" if is_adult else "false"), base_vars)
        if errors:
            return None, errors
        return data.get('Page'), None

    try:
        if not include_adult:
            data, errors = make_request(False)
            if errors:
                if show_error: st.error(f"API Error: {errors}")
                return None
            return data
        else:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_normal = executor.submit(make_request, False)
                future_adult = executor.submit(make_request, True)
                
                d_normal, e_normal = future_normal.result()
                d_adult, e_adult = future_adult.result()
            
            if e_normal and e_adult:
                if show_error: st.error(f"API Error: {e_normal}")
                return None
                
            d_normal = d_normal or {}
            d_adult = d_adult or {}
            
            combined_media = d_normal.get('media', []) + d_adult.get('media', [])
            
            if "POPULARITY_DESC" in sort:
                combined_media.sort(key=lambda x: x.get('popularity', 0), reverse=True)
            elif "SCORE_DESC" in sort:
                combined_media.sort(key=lambda x: x.get('averageScore', 0) or 0, reverse=True)
            elif "START_DATE_DESC" in sort:
                combined_media.sort(key=lambda x: (
                    x.get('startDate', {}).get('year') or 0,
                    x.get('startDate', {}).get('month') or 0,
                    x.get('startDate', {}).get('day') or 0
                ), reverse=True)
            elif "TITLE_DESC" in sort:
                combined_media.sort(key=lambda x: (x['title']['native'] or x['title']['romaji'] or ""), reverse=True)
            
            return {
                "pageInfo": {
                    "lastPage": max(d_normal.get('pageInfo', {}).get('lastPage', 1), d_adult.get('pageInfo', {}).get('lastPage', 1)),
                    "hasNextPage": d_normal.get('pageInfo', {}).get('hasNextPage', False) or d_adult.get('pageInfo', {}).get('hasNextPage', False)
                },
                "media": combined_media[:per_page]
            }
    except Exception as e:
        if show_error: st.error(f"Fetch Error: {e}")
        return None

def fetch_random_anime(year=None, season=None, genres=None, ex_genres=None, search=None, ids=None, exclude_ids=None, include_adult=False):
    current_sort = "POPULARITY_DESC"
    
    for attempt in range(10):
        first_page = fetch_anime(1, current_sort, year, season, genres, ex_genres, search, ids, exclude_ids, include_adult, per_page=1, show_error=False)
        if not first_page or not first_page.get('media'):
            continue
        
        last_page = first_page['pageInfo']['lastPage']
        max_safe_page = min(last_page, 4800 // 24)
        random_p = random.randint(1, max_safe_page)
        
        result = fetch_anime(random_p, current_sort, year, season, genres, ex_genres, search, ids, exclude_ids, include_adult, show_error=False)
        if result and result.get('media'):
            random.shuffle(result['media'])
            return result
    
    return None

# 5. 사이드바 UI
with st.sidebar:
    st.header("👤 계정")
    if not st.session_state.logged_in:
        flow = get_google_auth_flow()
        if flow:
            if 'google_auth_url' not in st.session_state or st.session_state.code_verifier is None:
                auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
                st.session_state.google_auth_url = auth_url
                st.session_state.code_verifier = flow.code_verifier
                oauth_storage[state] = flow.code_verifier
            
            st.markdown(f'<a href="{st.session_state.google_auth_url}" target="_self" class="google-login-btn">구글 로그인</a>', unsafe_allow_html=True)
    else:
        st.success(f"**{st.session_state.user_info.get('name')}**님")
        
        # --- 시청 통계 섹션 ---
        current_watched = st.session_state.watched_list or {}
        watched_count = len(current_watched)
        
        if "stats_cache" not in st.session_state:
            st.session_state.stats_cache = {"hash": None, "data": None}
            
        current_hash = hash(("v3", frozenset((k, v.get('rating', 0), v.get('count', 1)) for k, v in current_watched.items())))
        
        if st.session_state.stats_cache["hash"] != current_hash:
            if watched_count > 0:
                stats_pbar = st.empty()
                with st.spinner("통계 분석 중..."):
                    actually_watched = {k: v for k, v in current_watched.items() if v.get('status', 'watched') == 'watched'}
                    watched_count_stats = len(actually_watched)
                    
                    if watched_count_stats > 0:
                        avg_score = sum(v.get('rating', 0) for v in actually_watched.values()) / watched_count_stats
                        watched_ids = [int(aid) for aid in actually_watched.keys()]
                        meta_map = get_watched_metadata(watched_ids, p_bar_container=stats_pbar)
                        stats_pbar.empty()
                        
                        total_minutes = 0
                        genre_stats = {} 
                        
                        parent = {aid: aid for aid in watched_ids}
                        def find(i):
                            if parent[i] == i: return i
                            parent[i] = find(parent[i])
                            return parent[i]
                        def union(i, j):
                            root_i = find(i); root_j = find(j)
                            if root_i != root_j: parent[root_i] = root_j

                        related_to_watched = {}
                        valid_rel_types = ['PREQUEL', 'SEQUEL', 'PARENT','SUMMARY']
                        
                        for aid in watched_ids:
                            meta = meta_map.get(aid)
                            if not meta: continue
                            if aid not in related_to_watched: related_to_watched[aid] = set()
                            related_to_watched[aid].add(aid)
                            for edge in meta.get('relations', []):
                                rel_id = edge['node']['id']
                                if edge['relationType'] in valid_rel_types:
                                    if rel_id not in related_to_watched: related_to_watched[rel_id] = set()
                                    related_to_watched[rel_id].add(aid)
                        
                        for rel_id, aids in related_to_watched.items():
                            aids_list = list(aids)
                            for i in range(len(aids_list) - 1):
                                union(aids_list[i], aids_list[i+1])
                        
                        series_count = len(set(find(aid) for aid in watched_ids))

                        total_episodes = 0
                        quarterly_stats = {}
                        for aid, info in actually_watched.items():
                            meta = meta_map.get(aid)
                            rating = info.get('rating', 0)
                            if meta:
                                count = info.get('count', 1)
                                eps = meta.get('episodes') or 0
                                total_episodes += eps * count
                                total_minutes += eps * (meta.get('duration') or 0) * count
                                
                                y = meta.get('seasonYear')
                                s = meta.get('season')
                                if y:
                                    q_key = (int(y), s)
                                    if q_key not in quarterly_stats: quarterly_stats[q_key] = [0.0, 0]
                                    quarterly_stats[q_key][0] += rating
                                    quarterly_stats[q_key][1] += 1

                                for g in meta.get('genres', []):
                                    if g == "Hentai": continue
                                    ko_g = KO_GENRE_MAP.get(g, g)
                                    if ko_g not in genre_stats: genre_stats[ko_g] = [0, 0]
                                    genre_stats[ko_g][0] += rating
                                    genre_stats[ko_g][1] += 1
                        
                        sorted_genres = sorted(genre_stats.items(), key=lambda x: x[1][1], reverse=True)
                        
                        st.session_state.stats_cache = {
                            "hash": current_hash,
                            "data": {
                                "avg_score": avg_score,
                                "series_count": series_count,
                                "total_episodes": total_episodes,
                                "total_minutes": total_minutes,
                                "sorted_genres": sorted_genres,
                                "watched_count_stats": watched_count_stats,
                                "quarterly_stats": quarterly_stats
                            }
                        }
                    else:
                        st.session_state.stats_cache = {
                            "hash": current_hash,
                            "data": {
                                "avg_score": 0, "series_count": 0, "total_episodes": 0, "total_minutes": 0, "sorted_genres": [], "watched_count_stats": 0, "quarterly_stats": {}
                            }
                        }
            else:
                st.session_state.stats_cache = {
                    "hash": current_hash,
                    "data": {
                        "avg_score": 0, "series_count": 0, "total_episodes": 0, "total_minutes": 0, "sorted_genres": [], "watched_count_stats": 0, "quarterly_stats": {}
                    }
                }

        stats = st.session_state.stats_cache["data"] or {
            "avg_score": 0, "series_count": 0, "total_episodes": 0, "total_minutes": 0, "sorted_genres": [], "watched_count_stats": 0, "quarterly_stats": {}
        }
        avg_score = stats["avg_score"]
        series_count = stats["series_count"]
        total_episodes = stats.get("total_episodes", 0)
        total_minutes = stats["total_minutes"]
        sorted_genres = stats["sorted_genres"]
        watched_count_display = stats.get("watched_count_stats", 0)
        quarterly_stats = stats.get("quarterly_stats", {})

        # 1. 설정 팝오버 (시간 단위 + 플랫폼 커스텀)
        st.write("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col_title, col_opt = st.columns([3, 1])
        with col_title:
            st.markdown('<div style="font-size: 0.9rem; font-weight: bold; margin-top: 5px;">📊 나의 아카이브 현황</div>', unsafe_allow_html=True)
        with col_opt:
            with st.popover("⚙️", help="설정"):
                st.markdown("**⏱️ 시청 시간 단위**")
                t_unit = st.selectbox("시간 단위", ["일", "시간", "분", "초"], 
                                      index=["일", "시간", "분", "초"].index(st.session_state.time_unit), 
                                      key="time_unit_selector",
                                      label_visibility="collapsed")
                if t_unit != st.session_state.time_unit:
                    st.session_state.time_unit = t_unit
                    update_user_setting("time_unit", t_unit)

                st.divider()

                st.markdown("**📺 시청 플랫폼 설정**")
                all_plat_map = dict(DEFAULT_PLATFORMS, **st.session_state.custom_platforms)
                chosen_plats = st.multiselect(
                    "표시할 플랫폼 선택",
                    options=list(all_plat_map.keys()),
                    default=[p for p in st.session_state.selected_platforms if p in all_plat_map],
                    key="platform_multiselect"
                )
                if chosen_plats != st.session_state.selected_platforms:
                    st.session_state.selected_platforms = chosen_plats
                    update_user_setting("selected_platforms", chosen_plats)
                    st.rerun()

                with st.expander("➕ 새 플랫폼 직접 추가"):
                    c_name = st.text_input("플랫폼 이름", placeholder="예: 넷플릭스", key="new_plat_name")
                    c_url = st.text_input("검색 URL ({query} 포함)", placeholder="https://example.com/search?q={query}", key="new_plat_url")
                    
                    if st.button("플랫폼 추가", use_container_width=True):
                        if c_name and c_url and "{query}" in c_url:
                            st.session_state.custom_platforms[c_name] = c_url
                            if c_name not in st.session_state.selected_platforms:
                                st.session_state.selected_platforms.append(c_name)
                            update_user_setting("custom_platforms", st.session_state.custom_platforms)
                            update_user_setting("selected_platforms", st.session_state.selected_platforms)
                            st.toast(f"✅ '{c_name}' 플랫폼이 추가되었습니다.")
                            st.rerun()
                        else:
                            st.error("이름과 `{query}`가 포함된 URL을 입력해주세요.")

        # 2. 시간 포맷팅 계산
        if st.session_state.time_unit == "일": total_time_str = f"{total_minutes / 1440:.1f}일"
        elif st.session_state.time_unit == "시간": total_time_str = f"{total_minutes / 60:.1f}시간"
        elif st.session_state.time_unit == "분": total_time_str = f"{total_minutes:,}분"
        elif st.session_state.time_unit == "초": total_time_str = f"{total_minutes * 60:,}초"
        else: total_time_str = f"{total_minutes / 60:.1f}시간"

        # 3. 통합 통계 카드
        st.markdown(f"""
        <div style="background: rgba(76, 175, 80, 0.1); padding: 15px; border-radius: 12px; border: 1px solid rgba(76, 175, 80, 0.2); margin-bottom: 15px;">
            <!-- 상단 3칸 -->
            <div style="display: flex; justify-content: space-around; align-items: center; text-align: center; margin-bottom: 15px;">
                <div>
                    <div style="font-size: 1.2rem; font-weight: bold; color: #4CAF50;">{watched_count_display}</div>
                    <div style="font-size: 0.65rem; color: var(--secondary-text-color);">시청 작품</div>
                </div>
                <div style="border-left: 1px solid rgba(76, 175, 80, 0.2); height: 25px;"></div>
                <div>
                    <div style="font-size: 1.2rem; font-weight: bold; color: #2E7D32;">{series_count}</div>
                    <div style="font-size: 0.65rem; color: var(--secondary-text-color);">시리즈</div>
                </div>
                <div style="border-left: 1px solid rgba(76, 175, 80, 0.2); height: 25px;"></div>
                <div>
                    <div style="font-size: 1.2rem; font-weight: bold; color: #2E7D32;">{total_episodes}</div>
                    <div style="font-size: 0.65rem; color: var(--secondary-text-color);">시청 화수</div>
                </div>
            </div>
            <!-- 하단 2칸 -->
            <div style="border-top: 1px dashed rgba(76, 175, 80, 0.2); padding-top: 15px; display: flex; justify-content: space-around; align-items: center; text-align: center;">
                <div style="flex: 1;">
                    <div style="font-size: 1.1rem; font-weight: bold; color: #4CAF50;">{total_time_str}</div>
                    <div style="font-size: 0.65rem; color: var(--secondary-text-color);">총 시청 시간</div>
                </div>
                <div style="border-left: 1px solid rgba(76, 175, 80, 0.2); height: 25px;"></div>
                <div style="flex: 1;">
                    <div style="font-size: 1.1rem; font-weight: bold; color: #f39c12;">{avg_score:.2f}</div>
                    <div style="font-size: 0.65rem; color: var(--secondary-text-color);">평균 평점</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📊 장르별 상세 분석"):
            if watched_count > 0:
                for g_name, g_data in sorted_genres:
                    g_avg = g_data[0] / g_data[1]
                    g_count = g_data[1]
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #eee;">
                        <span style="font-weight: 600; font-size: 0.9rem;">{g_name}</span>
                        <div style="text-align: right;">
                            <span style="color: #2e7d32; font-size: 0.85rem; font-weight: bold;">{g_count}작품</span>
                            <span style="color: #f39c12; font-size: 0.85rem; margin-left: 8px;">★ {g_avg:.2f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("데이터가 없습니다.")

        with st.expander("📅 분기별 시청 통계"):
            if quarterly_stats:
                years_sorted = sorted(set(y for y, s in quarterly_stats.keys()), reverse=True)
                for y in years_sorted:
                    year_total = sum((d[1] if isinstance(d, (list, tuple)) else d) for (yr, s), d in quarterly_stats.items() if yr == y)
                    with st.expander(f"{y}년 ({year_total}작품)"):
                        for s_val, s_lab in [("WINTER", "1분기"), ("SPRING", "2분기"), ("SUMMER", "3분기"), ("FALL", "4분기")]:
                            q_data = quarterly_stats.get((y, s_val))
                            if q_data and isinstance(q_data, (list, tuple)):
                                r_sum, count = q_data
                                q_avg = r_sum / count
                                st.markdown(f"""
                                <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 4px; border-bottom: 1px solid #eee;">
                                    <div style="flex: 0 0 auto;">
                                        <a href="?year_filter={y}&season_filter={s_lab}" target="_self" style="text-decoration: none; color: inherit; font-weight: 600; font-size: 0.9rem;">{s_lab}</a>
                                    </div>
                                    <div class="q-stat-text" style="text-align: right;">
                                        <span style="color: #2e7d32; font-size: 0.85rem; font-weight: bold;">{count}작품</span>
                                        <span style="color: #f39c12; font-size: 0.85rem; margin-left: 8px;">★ {q_avg:.2f}</span>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                if st.button(f"선택: {s_lab}", key=f"q_filter_btn_{y}_{s_val}", use_container_width=True):
                                    st.session_state.year_filter = y
                                    st.session_state.season_filter = s_lab
                                    if st.session_state.logged_in:
                                        st.session_state.watch_filter = "본 작품만"
                                    st.rerun()
            else:
                st.caption("시청 완료 데이터가 없습니다.")

        # --- 데이터 내보내기/가져오기 섹션 ---
        with st.expander("💾 데이터 내보내기/가져오기"):
            if watched_count > 0:
                if st.button("📦 내보낼 데이터 준비하기", use_container_width=True):
                    with st.spinner("작품 정보를 불러오는 중..."):
                        watched_ids = list(current_watched.keys())
                        meta_map = get_watched_metadata(watched_ids)
                        
                        export_dict = {}
                        for aid, info in current_watched.items():
                            meta = meta_map.get(aid, {})
                            export_dict[str(aid)] = {
                                "title": meta.get("title", {"native": "Unknown", "romaji": "Unknown"}),
                                "rating": info.get("rating", 5.0),
                                "comment": info.get("comment", ""),
                                "count": info.get("count", 1)
                            }
                        
                        json_str = json.dumps(export_dict, ensure_ascii=False, indent=2)
                        st.download_button(
                            label="📥 JSON 다운로드",
                            data=json_str,
                            file_name=f"anime_archive_{datetime.now().strftime('%Y%m%d')}.json",
                            mime="application/json",
                            use_container_width=True
                        )
            else:
                st.caption("내보낼 데이터가 없습니다.")
            
            st.divider()
            
            uploaded_file = st.file_uploader("JSON 파일 가져오기", type=["json"], help="기존에 내보낸 JSON 파일을 업로드하세요.")
            if uploaded_file:
                try:
                    import_data = json.load(uploaded_file)
                    if st.button("🚀 데이터 병합 및 업로드", use_container_width=True, type="primary"):
                        valid_data = {}
                        for k, v in import_data.items():
                            try:
                                aid = int(k)
                                valid_data[aid] = {
                                    "rating": float(v.get("rating", 5.0)),
                                    "comment": str(v.get("comment", "")),
                                    "count": int(v.get("count", 1))
                                }
                            except: continue
                        
                        if valid_data:
                            if st.session_state.watched_list is None:
                                st.session_state.watched_list = {}
                            
                            st.session_state.watched_list.update(valid_data)
                            batch_update_db(st.session_state.watched_list)
                            st.success(f"✅ {len(valid_data)}개의 데이터를 성공적으로 가져왔습니다!")
                            st.rerun()
                        else:
                            st.error("가져올 수 있는 유효한 데이터가 없습니다.")
                except Exception as e:
                    st.error(f"파일 처리 오류: {e}")

        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("🔄 동기화", use_container_width=True, help="서버에서 시청 기록을 다시 불러옵니다."):
                with st.spinner("불러오는 중..."):
                    try:
                        load_user_data_from_db.clear()
                        user_email = st.session_state.user_info.get("email")
                        sync_user_data_to_session(user_email)
                        st.toast(f"✅ 동기화 완료!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"동기화 오류: {str(e)}")
        with sc2:
            if st.button("로그아웃", use_container_width=True):
                st.query_params["logout"] = "true"
                cookie_name = "anime_user_session"
                try:
                    cookie_manager.delete(cookie_name)
                except: pass
                
                st.components.v1.html(f"""
                    <script>
                        document.cookie = "{cookie_name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=None; Secure";
                        document.cookie = "user_{app_id}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=None; Secure";
                    </script>
                """, height=0)

                st.session_state.logged_in = False
                st.session_state.user_info = None
                st.session_state.watched_list = {}
                st.session_state.logout_clicked = True
                
                st.success("로그아웃 되었습니다.")
                st.rerun()

    st.divider()
    st.header("🔍 검색 및 필터")

    def reset_all_filters():
        if "q" in st.query_params:
            del st.query_params["q"]
        
        st.session_state.search_input = ""
        st.session_state.prev_q = ""
        st.session_state.year_filter = "전체"
        st.session_state.season_filter = "전체"
        st.session_state.genre_filter = []
        st.session_state.ex_genre_filter = []
        if st.session_state.logged_in:
            st.session_state.watch_filter = "전체"
        
        if "rating_filter" in st.session_state:
            st.session_state.rating_filter = 0.0
        
        st.session_state.all_media = []
        st.session_state.page = 1
        st.session_state.api_page = 1

    search_q = st.query_params.get("q", "")
    
    if "prev_q" not in st.session_state:
        st.session_state.prev_q = search_q
        
    if search_q != st.session_state.prev_q:
        st.session_state.search_input = search_q
        st.session_state.prev_q = search_q
        
    new_search = st.text_input("제목 검색", placeholder="영문 또는 일문 제목", key="search_input")

    st.components.v1.html("""
        <script>
            function setupInputs() {
                const doc = window.parent.document;
                const inputs = doc.querySelectorAll('input');
                
                inputs.forEach(input => {
                    if (input.placeholder === "영문 또는 일문 제목") {
                        input.type = "search";
                        input.setAttribute("enterkeyhint", "search");
                        input.addEventListener("keydown", (e) => {
                            if (e.key === "Enter") input.blur();
                        });
                        return;
                    }
                    
                    const container = input.closest('div[data-testid="stSelectbox"], div[data-testid="stMultiSelect"]');
                    if (container) {
                        const label = container.querySelector('label');
                        const labelText = label ? label.textContent.trim() : "";
                        const targetLabels = ["년도", "분기", "포함 장르", "제외 장르", "시청 여부", "시간 단위", "정렬 방식", "표시할 플랫폼 선택"];
                        
                        if (targetLabels.includes(labelText)) {
                            input.setAttribute('inputmode', 'none');
                            input.setAttribute('readonly', 'true');
                            input.style.cursor = 'pointer';
                        }
                    }
                });
            }

            setupInputs();

            const observer = new MutationObserver((mutations) => {
                setupInputs();
            });

            observer.observe(window.parent.document.body, {
                childList: true,
                subtree: true
            });
        </script>
    """, height=0)

    if new_search != search_q:
        st.query_params["q"] = new_search
        st.session_state.prev_q = new_search
        st.session_state.page = 1
        st.rerun()

    st.divider()
    years = ["전체"] + list(range(datetime.now().year, 1989, -1))
    s_year_val = st.selectbox("년도", years, key="year_filter")
    s_year = s_year_val if s_year_val != "전체" else None

    season_labels = ["전체", "1분기", "2분기", "3분기", "4분기"]
    season_values = [None, "WINTER", "SPRING", "SUMMER", "FALL"]
    season_map = dict(zip(season_labels, season_values))
    
    s_season_label = st.selectbox("분기", season_labels, key="season_filter")
    s_season = season_map[s_season_label]
    
    genre_map = {
        "액션": "Action", "모험": "Adventure", "코미디": "Comedy", "드라마": "Drama", "에치": "Ecchi",
        "판타지": "Fantasy", "공포": "Horror", "마법소녀": "Mahou Shoujo", "메카": "Mecha", 
        "음악": "Music", "미스터리": "Mystery", "심리": "Psychological", "로맨스": "Romance", 
        "SF": "Sci-Fi", "일상": "Slice of Life", "스포츠": "Sports", "초자연": "Supernatural", "스릴러": "Thriller"
    }
    selected_genres = st.multiselect("포함 장르", list(genre_map.keys()), key="genre_filter")
    s_genres = [genre_map[g] for g in selected_genres] if selected_genres else None

    excluded_genres = st.multiselect("제외 장르", list(genre_map.keys()), key="ex_genre_filter")
    s_ex_genres = [genre_map[g] for g in excluded_genres] if excluded_genres else None
    
    watch_options = ["전체", "본 작품만", "볼 작품만", "안 본 작품만"]
    s_watch = st.selectbox("시청 여부", watch_options, key="watch_filter") if st.session_state.logged_in else "전체"
    only_w = (s_watch == "본 작품만")
    only_wish = (s_watch == "볼 작품만")
    only_not_w = (s_watch == "안 본 작품만")

    if st.button("🔄 전체 필터 초기화", use_container_width=True, on_click=reset_all_filters):
        st.rerun()

    adult_param = st.query_params.get("adult", "false") == "true"
    s_adult = st.checkbox("성인물 포함", value=adult_param, key="adult_filter")

    if s_adult != adult_param:
        st.query_params["adult"] = "true" if s_adult else "false"
        if "sort_by" in st.session_state:
            st.query_params["sort"] = st.session_state.sort_by
        st.session_state.page = 1
        st.rerun()
    
    s_rating = 0.0

    st.divider()
    if st.button("🎲 랜덤 추천 받기", use_container_width=True, type="primary"):
        with st.spinner("랜덤 작품 찾는 중..."):
            target_ids = None
            exclude_ids = None
            current_watched = st.session_state.watched_list or {}
            
            if only_w:
                target_ids = [aid for aid, info in current_watched.items() if info.get('status', 'watched') == 'watched']
                if not target_ids: target_ids = [0]
                else: target_ids = target_ids[:500]
            
            if only_wish:
                target_ids = [aid for aid, info in current_watched.items() if info.get('status') == 'wish']
                if not target_ids: target_ids = [0]
                else: target_ids = target_ids[:500]
            
            if only_not_w:
                exclude_ids = list(current_watched.keys())
                if exclude_ids: exclude_ids = exclude_ids[:500]

            random_data = fetch_random_anime(
                s_year, s_season, s_genres, s_ex_genres,
                new_search if new_search else None,
                ids=target_ids,
                exclude_ids=exclude_ids,
                include_adult=s_adult
            )
            
            if random_data:
                st.session_state.all_media = random_data['media']
                st.session_state.is_random_mode = True
                st.session_state.random_media = None
                st.rerun()
            else:
                st.warning("조건에 맞는 작품이 없습니다.")

    if st.session_state.is_random_mode:
        if st.button("🔙 일반 목록으로", use_container_width=True):
            st.session_state.is_random_mode = False
            st.session_state.all_media = []
            st.rerun()

# 정렬 옵션 설정
sort_map = {"인기도순": "POPULARITY_DESC", "평점순": "SCORE_DESC", "방영일순": "START_DATE_DESC"}
if st.session_state.logged_in and only_w:
    sort_map["내 평점순"] = "MY_SCORE_DESC"
    sort_map["시청 순서순"] = "WATCH_AT_DESC"
else:
    if st.session_state.sort_by in ["내 평점순", "시청 순서순"]:
        st.session_state.sort_by = "인기도순"

current_filters = {
    "q": new_search, "y": s_year, "s": s_season, 
    "g": str(s_genres), "eg": str(s_ex_genres),
    "only_w": only_w, "only_wish": only_wish, "only_not_w": only_not_w, "adult": s_adult, "rating": s_rating,
    "sort": st.session_state.sort_by
}

if st.session_state.last_filters != current_filters:
    st.session_state.all_media = []
    st.session_state.page = 1
    st.session_state.api_page = 1
    st.session_state.last_filters = current_filters
    st.session_state.has_next = True
    st.session_state.is_random_mode = False
    st.session_state.random_media = None

# 데이터 로드
if st.session_state.has_next and (not st.session_state.all_media or len(st.session_state.all_media) < st.session_state.page * 24):
    target_ids = None
    exclude_ids = None
    
    current_watched = st.session_state.watched_list or {}
    if only_w:
        target_ids = [aid for aid, info in current_watched.items() if info.get('status', 'watched') == 'watched' and info.get('rating', 0) >= s_rating]
        
        if st.session_state.sort_by == "내 평점순":
            target_ids.sort(key=lambda aid: (
                current_watched[aid].get('rating', 0), 
                current_watched[aid].get('count', 1)
            ), reverse=True)
        elif st.session_state.sort_by == "시청 순서순":
            def get_sort_key(aid):
                val = current_watched[aid].get('at')
                if val is None: return datetime.min
                if isinstance(val, str):
                    try: return datetime.fromisoformat(val.replace('Z', '+00:00'))
                    except: return datetime.min
                if hasattr(val, 'tzinfo') and val.tzinfo is not None:
                    return val.replace(tzinfo=None)
                return val
            target_ids.sort(key=get_sort_key, reverse=True)
            
        if not target_ids: target_ids = [0]

    elif only_wish:
        target_ids = [aid for aid, info in current_watched.items() if info.get('status') == 'wish']
        target_ids.sort(key=lambda aid: current_watched[aid].get('at') or datetime.min, reverse=True)
        if not target_ids: target_ids = [0]
    
    if only_not_w:
        exclude_ids = list(current_watched.keys())
        if exclude_ids:
            exclude_ids = exclude_ids[:500]

    api_sort = sort_map.get(st.session_state.sort_by, "POPULARITY_DESC")
    is_custom_sort = (st.session_state.sort_by in ["내 평점순", "시청 순서순"] and only_w)
    has_active_filters = any([new_search, s_year, s_season, s_genres, s_ex_genres, s_rating > 0])
    
    if is_custom_sort:
        if has_active_filters:
            if not st.session_state.all_media:
                all_fetched = []
                temp_api_page = 1
                with st.spinner("조건에 맞는 시청 기록 찾는 중..."):
                    while True:
                        data = fetch_anime(
                            temp_api_page, "POPULARITY_DESC", 
                            s_year, s_season, s_genres, s_ex_genres,
                            new_search, ids=None, exclude_ids=exclude_ids,
                            include_adult=s_adult, per_page=50
                        )
                        if not data or not data['media']: break
                        
                        watched_only = [m for m in data['media'] if m['id'] in current_watched and current_watched[m['id']].get('status', 'watched') == 'watched' and current_watched[m['id']].get('rating', 0) >= s_rating]
                        all_fetched.extend(watched_only)
                        
                        if not data['pageInfo']['hasNextPage'] or len(all_fetched) >= 500: break
                        temp_api_page += 1
                
                if st.session_state.sort_by == "내 평점순":
                    all_fetched.sort(key=lambda x: (
                        current_watched.get(x['id'], {}).get('rating', 0),
                        current_watched.get(x['id'], {}).get('count', 1)
                    ), reverse=True)
                elif st.session_state.sort_by == "시청 순서순":
                    all_fetched.sort(key=lambda x: current_watched.get(x['id'], {}).get('at') or datetime.min, reverse=True)
                
                st.session_state.all_media = all_fetched
                st.session_state.has_next = False
                st.session_state.total_pages = 1
        else:
            per_page = 24
            start_idx = (st.session_state.page - 1) * per_page
            end_idx = start_idx + per_page
            
            paged_ids = target_ids[start_idx:end_idx]
            
            if paged_ids:
                data = fetch_anime(1, "POPULARITY_DESC", None, None, None, None, None, ids=paged_ids, per_page=24)
                if data and data['media']:
                    media_dict = {m['id']: m for m in data['media']}
                    sorted_new_items = []
                    for aid in paged_ids:
                        if aid in media_dict: sorted_new_items.append(media_dict[aid])
                    
                    existing_ids = {m['id'] for m in st.session_state.all_media}
                    for item in sorted_new_items:
                        if item['id'] not in existing_ids:
                            st.session_state.all_media.append(item)
                    
                    st.session_state.has_next = end_idx < len(target_ids)
                    st.session_state.total_pages = (len(target_ids) + per_page - 1) // per_page
    else:
        if api_sort == "MY_SCORE_DESC": api_sort = "POPULARITY_DESC"
        
        attempts = 0
        while st.session_state.has_next and len(st.session_state.all_media) < st.session_state.page * 24 and attempts < 5:
            attempts += 1
            fetch_size = 50 if (only_w or only_not_w) else 24
            api_ids = None if (only_w and has_active_filters) else target_ids
            
            data = fetch_anime(
                st.session_state.api_page, 
                api_sort, 
                s_year, s_season, s_genres, s_ex_genres,
                new_search,
                ids=api_ids,
                exclude_ids=exclude_ids,
                include_adult=s_adult,
                per_page=fetch_size
            )

            if data:
                new_items = data['media']
                if only_w and has_active_filters:
                    new_items = [m for m in new_items if m['id'] in current_watched and current_watched[m['id']].get('status', 'watched') == 'watched' and current_watched[m['id']].get('rating', 0) >= s_rating]
                elif only_not_w:
                    new_items = [m for m in new_items if m['id'] not in current_watched]
                
                existing_ids = {m['id'] for m in st.session_state.all_media}
                added_count = 0
                for item in new_items:
                    if item['id'] not in existing_ids:
                        st.session_state.all_media.append(item)
                        added_count += 1
                
                st.session_state.has_next = data['pageInfo']['hasNextPage']
                st.session_state.api_page += 1
                
                if added_count == 0 and st.session_state.has_next: continue
                else: break
            else: break

# --- 추천 정보 가져오기 (캐싱 적용) ---
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_recommendations(anime_id):
    query = '''
    query ($id: Int) {
      Media (id: $id) {
        recommendations (sort: RATING_DESC, perPage: 5) {
          nodes {
            mediaRecommendation {
              id
              title { native romaji }
              coverImage { large }
              siteUrl
            }
          }
        }
      }
    }
    '''
    data, errors = safe_anilist_request(query, {'id': anime_id})
    if data:
        nodes = data.get('Media', {}).get('recommendations', {}).get('nodes', [])
        return [node['mediaRecommendation'] for node in nodes if node.get('mediaRecommendation')]
    return []

# 7. 메인 화면 렌더링
anime_list = st.session_state.all_media
total_loaded = len(anime_list)

h_col1, h_col2 = st.columns([4, 1])
with h_col1:
    if st.session_state.is_random_mode:
        st.title(f"🎲 랜덤 추천 결과 ({total_loaded}개)", anchor=False)
    elif new_search:
        st.title(f"🔍 '{new_search}' 검색 결과 ({total_loaded}개)", anchor=False)
    else:
        title_parts = [] 
        if s_year: title_parts.append(str(s_year))
        if s_season_label != "전체": title_parts.append(s_season_label)
        title_text = " ".join(title_parts) if title_parts else "전체 목록"
        st.title(f"📅 {title_text} Archive ({total_loaded}개)", anchor=False)
with h_col2:
    st.write("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    if not st.session_state.is_random_mode:
        available_sorts = list(sort_map.keys())
        current_sort = st.session_state.sort_by
        if current_sort not in available_sorts:
            current_sort = available_sorts[0]
            st.session_state.sort_by = current_sort
            
        st.selectbox("정렬 방식", available_sorts, 
                     index=available_sorts.index(current_sort),
                     key="sort_selector",
                     on_change=lambda: st.session_state.update({"sort_by": st.session_state.sort_selector}),
                     label_visibility="collapsed")

st.divider()

if not anime_list: 
    st.info("데이터가 없습니다.")
else:
    for i in range(0, len(anime_list), 4):
        cols = st.columns(4)
        chunk = anime_list[i:i+4]
        for j, anime in enumerate(chunk):
            a_id = anime['id']
            current_watched = st.session_state.watched_list or {}
            with cols[j]:
                is_w = a_id in current_watched
                w_data = current_watched.get(a_id, {}) if is_w else {}
                status = w_data.get("status", "watched")
                
                # 1. 뱃지 HTML
                if is_w:
                    if status == "wish":
                        badge_html = '<div class="wish-badge">✓ 보관</div>'
                    elif status == "dropped":
                        drop_ep = w_data.get("count", 0)
                        ep_str = f" ({drop_ep}화)" if drop_ep > 0 else ""
                        badge_html = f'<div class="dropped-badge">✖ 하차{ep_str}</div>'
                    else:
                        user_rating = w_data.get("rating", 5.0)
                        user_count = w_data.get("count", 1)
                        count_str = f" ({user_count}회)" if user_count > 1 else ""
                        badge_html = f'<div class="watched-badge">✓ {user_rating:.1f}점{count_str}</div>'
                else:
                    badge_html = '<div style="height:1.5rem; margin-bottom:5px;"></div>'

                # 2. 제목 및 포맷 정보
                title = anime['title']['native'] or anime['title']['romaji']
                f_map = {"TV": "TV", "TV_SHORT": "TV (Short)", "MOVIE": "영화", "SPECIAL": "특별편", "OVA": "OVA", "ONA": "ONA", "MUSIC": "뮤직"}
                a_format = f_map.get(anime.get('format'), anime.get('format') or "Unknown")
                
                # 3. 년도/분기 및 평점 별점
                s_map = {"WINTER": "1분기", "SPRING": "2분기", "SUMMER": "3분기", "FALL": "4분기"}
                a_year = anime.get('seasonYear') or "미정"
                a_season = s_map.get(anime.get('season'), "")
                
                raw_score = anime.get('averageScore')
                if raw_score:
                    score_5 = round(raw_score / 20, 1)
                    stars = "★" * int(score_5) + "☆" * (5 - int(score_5))
                    score_html = f"<div class='score-box'>{stars} {score_5}</div>"
                else:
                    score_html = "<div class='score-box' style='color:#bbb;'>☆☆☆☆☆ 0.0</div>"

                # 4. 코멘트 영역 (줄바꿈 허용, 기울임/따옴표 제거)
                user_comment = w_data.get("comment", "")
                if is_w and user_comment:
                    comment_html = f'<div class="user-comment-box">{user_comment}</div>'
                else:
                    comment_html = '<div class="empty-comment-box"></div>'

                # 5. 통합 렌더링
                cover_img = anime.get('coverImage', {}).get('extraLarge') or anime.get('coverImage', {}).get('large')
                st.image(cover_img, use_container_width=True)
                st.markdown(f"""
                <div class="anime-card-container">
                    {badge_html}
                    <div class='anime-title-box'>{title}</div>
                    <div style='font-size: 0.75rem; color: #888; margin-top: -10px; margin-bottom: 5px;'>{a_format}</div>
                    <div class='anime-info-box'>📅 {a_year}년 {a_season}</div>
                    {score_html}
                    {comment_html}
                </div>
                """, unsafe_allow_html=True)

                c1, c2, c3 = st.columns(3, gap="small")
                
                # 상세 팝오버
                with c1.popover("상세", use_container_width=True, key=f"pop_detail_{a_id}"):
                    genres = [g for g in anime.get('genres', []) if g != "Hentai"]
                    if genres:
                        g_cols = st.columns(3, gap="small")
                        for idx, g in enumerate(genres):
                            ko_g = KO_GENRE_MAP.get(g, g)
                            with g_cols[idx % 3]:
                                if st.button(ko_g, key=f"g_btn_{a_id}_{g}", use_container_width=True):
                                    if ko_g not in st.session_state.genre_filter:
                                        st.session_state.genre_to_add = ko_g
                                        st.rerun()
                        st.write("")

                    st.link_button("AniList에서 보기", anime['siteUrl'], use_container_width=True)
                    
                    if st.button("🔍 이름으로 검색", key=f"btn_search_{a_id}", use_container_width=True, type="primary"):
                        title = anime['title']['native'] or anime['title']['romaji']
                        st.query_params["q"] = title
                        st.session_state.all_media = []
                        st.session_state.page = 1
                        st.rerun()
                
                # 동적 플랫폼 검색 팝오버 (🔍)
                with c2.popover("🔍", use_container_width=True, key=f"search_pop_{a_id}"):
                    st.markdown("**📺 시청 플랫폼 선택**")
                    search_title = anime['title']['native'] or anime['title']['romaji']
                    encoded_title = urllib.parse.quote(search_title)
                    
                    all_plat_map = dict(DEFAULT_PLATFORMS, **st.session_state.custom_platforms)
                    active_plats = [p for p in st.session_state.selected_platforms if p in all_plat_map]
                    
                    if active_plats:
                        for p_name in active_plats:
                            target_template = all_plat_map[p_name]
                            target_url = target_template.format(query=encoded_title)
                            st.link_button(f"🌐 {p_name} 검색", target_url, use_container_width=True)
                    else:
                        st.caption("선택된 플랫폼이 없습니다. 상단 설정(⚙️)에서 플랫폼을 추가하세요.")

                if st.session_state.logged_in:
                    ac = st.session_state.action_cnt
                    pop_label = "수정" if is_w and status == "watched" else ("보관" if is_w and status == "wish" else ("하차" if is_w and status == "dropped" else "시청"))
                    
                    with c3.popover(pop_label, use_container_width=True, key=f"pop_act_{a_id}_{ac}"):
                        if is_w and status == "watched":
                            w_data = current_watched.get(a_id, {})
                            u_score = st.slider("내 평점", 0.0, 5.0, round(float(w_data.get("rating", 5.0)), 1), 0.1, format="%.1f", key=f"score_edit_{a_id}_{ac}")
                            u_count = st.number_input("시청 횟수", min_value=1, value=int(w_data.get("count", 1)), step=1, key=f"count_edit_{a_id}_{ac}")
                            u_comment = st.text_area("코멘트", value=w_data.get("comment", ""), placeholder="짧은 감상평을 남겨주세요", key=f"comm_edit_{a_id}_{ac}")
                            
                            if st.button("업데이트", key=f"btn_update_{a_id}_{ac}", use_container_width=True, type="primary"):
                                if st.session_state.watched_list is None: st.session_state.watched_list = {}
                                st.session_state.watched_list[a_id] = {"rating": u_score, "comment": u_comment, "count": u_count, "status": "watched"}
                                update_db(a_id, "add", u_score, u_comment, u_count, status="watched")
                                st.session_state.action_cnt += 1
                                st.rerun()
                                
                            st.divider()
                            if st.button("시청 기록 삭제", key=f"btn_delete_{a_id}_{ac}", use_container_width=True):
                                if st.session_state.watched_list is not None:
                                    st.session_state.watched_list.pop(a_id, None)
                                update_db(a_id, "remove")
                                st.session_state.action_cnt += 1
                                st.rerun()
                        elif is_w and (status == "wish" or status == "dropped"):
                            u_score = st.slider("내 평점", 0.0, 5.0, 5.0, 0.1, format="%.1f", key=f"score_wish_to_w_{a_id}_{ac}")
                            u_count = st.number_input("시청 횟수", min_value=1, value=1, step=1, key=f"count_wish_to_w_{a_id}_{ac}")
                            u_comment = st.text_area("코멘트", value=w_data.get("comment", ""), placeholder="짧은 감상평을 남겨주세요", key=f"comm_wish_to_w_{a_id}_{ac}")
                            
                            if st.button("시청 완료로 기록", key=f"btn_wish_to_w_{a_id}_{ac}", use_container_width=True, type="primary"):
                                if st.session_state.watched_list is None: st.session_state.watched_list = {}
                                st.session_state.watched_list[a_id] = {"rating": u_score, "comment": u_comment, "count": u_count, "status": "watched"}
                                update_db(a_id, "add", u_score, u_comment, u_count, status="watched")
                                st.session_state.action_cnt += 1
                                st.rerun()
                            
                            bu1, bu2 = st.columns(2)
                            with bu1:
                                if status == "wish":
                                    if st.button("하차로 변경", key=f"btn_wish_to_drop_{a_id}_{ac}", use_container_width=True):
                                        st.session_state.watched_list[a_id] = {"rating": 0.0, "comment": u_comment, "count": u_count, "status": "dropped"}
                                        update_db(a_id, "add", 0.0, u_comment, u_count, status="dropped")
                                        st.session_state.action_cnt += 1
                                        st.rerun()
                                elif status == "dropped":
                                    if st.button("보관으로 변경", key=f"btn_drop_to_wish_{a_id}_{ac}", use_container_width=True):
                                        st.session_state.watched_list[a_id] = {"rating": 0.0, "comment": u_comment, "count": 0, "status": "wish"}
                                        update_db(a_id, "add", 0.0, u_comment, 0, status="wish")
                                        st.session_state.action_cnt += 1
                                        st.rerun()
                            
                            with bu2:
                                if st.button("코멘트 업데이트", key=f"btn_comm_update_{a_id}_{ac}", use_container_width=True):
                                    st.session_state.watched_list[a_id]["comment"] = u_comment
                                    update_db(a_id, "add", 0.0, u_comment, w_data.get("count", 0), status=status)
                                    st.session_state.action_cnt += 1
                                    st.rerun()

                            st.divider()
                            del_label = "보관 취소" if status == "wish" else "하차 취소"
                            if st.button(del_label, key=f"btn_wish_del_{a_id}_{ac}", use_container_width=True):
                                if st.session_state.watched_list is not None:
                                    st.session_state.watched_list.pop(a_id, None)
                                update_db(a_id, "remove")
                                st.session_state.action_cnt += 1
                                st.rerun()
                        else:
                            u_score = st.slider("내 평점", 0.0, 5.0, 5.0, 0.1, format="%.1f", key=f"score_new_{a_id}_{ac}")
                            u_count = st.number_input("시청 횟수 / 마지막 화수", min_value=1, value=1, step=1, key=f"count_new_{a_id}_{ac}")
                            u_comment = st.text_area("코멘트", placeholder="짧은 감상평을 남겨주세요", key=f"comm_new_{a_id}_{ac}")
                            
                            if st.button("저장", key=f"btn_save_{a_id}_{ac}", use_container_width=True, type="primary"):
                                if st.session_state.watched_list is None: st.session_state.watched_list = {}
                                st.session_state.watched_list[a_id] = {"rating": u_score, "comment": u_comment, "count": u_count, "status": "watched"}
                                update_db(a_id, "add", u_score, u_comment, u_count, status="watched")
                                st.session_state.action_cnt += 1
                                st.rerun()
                            
                            bw1, bw2 = st.columns(2)
                            with bw1:
                                if st.button("보관", key=f"btn_wish_{a_id}_{ac}", use_container_width=True):
                                    if st.session_state.watched_list is None: st.session_state.watched_list = {}
                                    st.session_state.watched_list[a_id] = {"rating": 0.0, "comment": u_comment, "count": 0, "status": "wish"}
                                    update_db(a_id, "add", 0.0, u_comment, 0, status="wish")
                                    st.session_state.action_cnt += 1
                                    st.rerun()
                            with bw2:
                                if st.button("하차", key=f"btn_drop_{a_id}_{ac}", use_container_width=True):
                                    if st.session_state.watched_list is None: st.session_state.watched_list = {}
                                    st.session_state.watched_list[a_id] = {"rating": 0.0, "comment": u_comment, "count": u_count, "status": "dropped"}
                                    update_db(a_id, "add", 0.0, u_comment, u_count, status="dropped")
                                    st.session_state.action_cnt += 1
                                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            st.write("") 

    # 하단 네비게이션 로직
    st.write("---")
    if st.session_state.is_random_mode:
        if st.button("🎲 랜덤 작품 더 보기", use_container_width=True):
            with st.spinner("새로운 랜덤 작품 찾는 중..."):
                target_ids = None
                exclude_ids = None
                current_watched = st.session_state.watched_list or {}
                
                if only_w:
                    target_ids = [aid for aid, info in current_watched.items() if info.get('status', 'watched') == 'watched' and info.get('rating', 0) >= s_rating]
                    if not target_ids: target_ids = [0]
                    else: target_ids = target_ids[:500]
                
                if only_not_w:
                    exclude_ids = list(current_watched.keys())
                    if exclude_ids: exclude_ids = exclude_ids[:500]

                new_random = fetch_random_anime(
                    s_year, s_season, s_genres, s_ex_genres,
                    new_search if new_search else None,
                    ids=target_ids,
                    exclude_ids=exclude_ids,
                    include_adult=s_adult
                )
                if new_random:
                    existing_ids = {m['id'] for m in st.session_state.all_media}
                    for item in new_random['media']:
                        if item['id'] not in existing_ids:
                            st.session_state.all_media.append(item)
                    st.rerun()
                else:
                    st.warning("추가할 수 있는 작품이 없습니다.")
    else:
        if st.session_state.has_next:
            if st.button("작품 더 보기", use_container_width=True):
                st.session_state.page += 1
                st.rerun()
        else:
            st.info("모든 작품을 불러왔습니다.")
