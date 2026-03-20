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
        font-size: 0.85rem; color: var(--text-color); font-style: italic;
        height: 65px; overflow-y: auto;
        box-sizing: border-box;
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
</style>
""", unsafe_allow_html=True)

# 0. 글로벌 인증 저장소 (세션 유실 시에도 서버 메모리에 보존)
@st.cache_resource
def get_oauth_storage():
    return {}

oauth_storage = get_oauth_storage()

# 2. Firebase 초기화 (Secrets 구조 보정)
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        try:
            # AttrDict 및 중첩된 객체를 순수 dict/list/str로 변환하는 헬퍼 함수
            def clean_secrets(obj):
                if hasattr(obj, "to_dict"):
                    return clean_secrets(obj.to_dict())
                if isinstance(obj, dict):
                    return {k: clean_secrets(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [clean_secrets(i) for i in obj]
                return obj

            if "firebase_service_account" in st.secrets:
                # secrets에서 데이터를 가져와 순수 Python 객체로 변환
                sec = clean_secrets(st.secrets["firebase_service_account"])
                
                key_dict = None
                # Case 1: sec 자체가 JSON 문자열인 경우
                if isinstance(sec, str):
                    key_dict = json.loads(sec, strict=False)
                # Case 2: sec가 딕셔너리인 경우
                elif isinstance(sec, dict):
                    # 내부 키 "firebase_service_account"에 JSON 문자열이 있는 경우 (유저의 secrets.toml 구조)
                    inner = sec.get("firebase_service_account")
                    if isinstance(inner, str):
                        key_dict = json.loads(inner, strict=False)
                    # 내부 키 값이 이미 딕셔너리인 경우
                    elif isinstance(inner, dict):
                        key_dict = inner
                    # 섹션 자체가 서비스 계정 정보인 경우 (project_id 등이 직접 포함됨)
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
    """
    사용자 문서 1개만 읽어서 전체 목록과 설정을 가져옵니다. 
    할당량 초과 에러 발생 시 안내 메시지를 표시하고 크래시를 방지합니다.
    """
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
            return {}, {} # 빈 목록 반환하여 크래시 방지
        raise e

def sync_user_data_to_session(user_email):
    """DB에서 사용자 데이터를 가져와 세션에 동기화합니다."""
    watched, prefs = load_user_data_from_db(user_email)
    st.session_state.watched_list = watched
    if prefs and "time_unit" in prefs:
        st.session_state.time_unit = prefs["time_unit"]

def update_db(anime_id, action="add", rating=5.0, comment="", count=1):
    """백그라운드 쓰레드에서 DB를 업데이트하여 UI 차단을 방지합니다."""
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
                            "count": count
                        }
                    }
                }, merge=True)
            else:
                user_ref.update({
                    f"watched.{anime_id}": firestore.DELETE_FIELD
                })
        except Exception: pass

    # 쓰레드 시작 (백그라운드 작업)
    threading.Thread(target=run_in_thread, daemon=True).start()
    # 캐시 클리어는 즉시 수행하여 다음 로드 시 반영되도록 함
    load_user_data_from_db.clear()

def batch_update_db(data_dict):
    """대량의 데이터를 한 번에 업데이트합니다."""
    if not db or not st.session_state.get("logged_in"): return
    user_email = st.session_state.user_info.get("email")
    user_ref = db.collection("artifacts").document(app_id).collection("users").document(user_email)
    
    def run_in_thread():
        try:
            # Firestore에 저장할 때는 키가 문자열이어야 함
            db_data = {}
            for aid, info in data_dict.items():
                db_data[str(aid)] = {
                    "id": int(aid),
                    "at": datetime.now(),
                    "rating": float(info.get('rating', 5.0)),
                    "comment": str(info.get('comment', "")),
                    "count": int(info.get('count', 1))
                }
            user_ref.set({"watched": db_data}, merge=True)
        except Exception: pass

    threading.Thread(target=run_in_thread, daemon=True).start()
    load_user_data_from_db.clear()

def update_user_setting(key, value):
    """사용자 설정을 DB에 백그라운드에서 저장합니다."""
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
            # 429 Too Many Requests 처리
            if res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", 1))
                import time
                time.sleep(retry_after + i) # 점진적으로 대기 시간 증가
                continue
            
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
    """API에서 메타데이터를 가져오는 핵심 로직 (글로벌 캐시 적용)"""
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
    """세션 캐시와 글로벌 캐시를 조합하여 메타데이터를 반환합니다. 진행률 표시 기능을 지원합니다."""
    if not ids: return {}
    if "metadata_storage" not in st.session_state:
        st.session_state.metadata_storage = {}
        
    clean_ids = list(set(int(x) for x in ids))
    missing_ids = [i for i in clean_ids if i not in st.session_state.metadata_storage]
    
    if missing_ids:
        # 50개씩 청크 분할
        chunks = [missing_ids[i:i+50] for i in range(0, len(missing_ids), 50)]
        total_chunks = len(chunks)
        
        # 병렬 작업 수행 (Workers를 10개로 늘려 속도 향상)
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
    # None으로 초기화하여 "데이터를 아직 안 불러옴"과 "목록이 비어있음"을 구분 (DB 읽기 최적화)
    st.session_state.watched_list = None
    st.session_state.auth_checked = False
    st.session_state.logout_clicked = False # 로그아웃 플래그 추가

if 'all_media' not in st.session_state: st.session_state.all_media = []
if 'random_media' not in st.session_state: st.session_state.random_media = None
if 'is_random_mode' not in st.session_state: st.session_state.is_random_mode = False
if 'page' not in st.session_state: st.session_state.page = 1
if 'api_page' not in st.session_state: st.session_state.api_page = 1 # 실제 API에서 불러올 페이지 번호
if 'has_next' not in st.session_state: st.session_state.has_next = True
if 'last_filters' not in st.session_state: st.session_state.last_filters = {}
if 'sort_by' not in st.session_state: st.session_state.sort_by = "인기도순"
if 'total_pages' not in st.session_state: st.session_state.total_pages = 1
if 'action_cnt' not in st.session_state: st.session_state.action_cnt = 0
if 'time_unit' not in st.session_state: st.session_state.time_unit = "시간"

# --- [앱 보호막: 인증 확인 전까지 UI 차단] ---
def run_auth_shield():
    # 1. URL에 logout=true가 있으면 자동 로그인 차단
    if st.query_params.get("logout") == "true":
        return False

    # 2. 이미 로그인된 세션이면 통과
    if st.session_state.get('logged_in'):
        return True
    
    # 3. 구글 OAuth 콜백 처리 (새로운 로그인 시도 시)
    auth_code = st.query_params.get("code")
    auth_state = st.query_params.get("state")
    
    if auth_code and auth_state:
        # oauth_storage에서 code_verifier를 꺼내오면서 즉시 삭제 (중복 사용 방지)
        code_verifier = oauth_storage.pop(auth_state, None)
        if code_verifier:
            try:
                flow = get_google_auth_flow()
                if flow:
                    flow.fetch_token(code=auth_code, code_verifier=code_verifier)
                    credentials = flow.credentials
                    
                    # ID 토큰 검증 및 사용자 정보 추출
                    id_info = id_token.verify_oauth2_token(
                        credentials.id_token, GoogleRequest(), flow.client_config['client_id']
                    )
                    
                    user_info = {
                        "email": id_info.get("email"),
                        "name": id_info.get("name"),
                        "picture": id_info.get("picture")
                    }
                    
                    # 세션 저장
                    st.session_state.user_info = user_info
                    st.session_state.logged_in = True
                    
                    # 1. 컴포넌트 방식으로 쿠키 저장
                    user_key = "anime_user_session"
                    expires = datetime.now() + timedelta(days=30)
                    cookie_manager.set(
                        user_key, 
                        user_info, 
                        expires_at=expires,
                        key="save_user_cookie"
                    )
                    
                    # 2. 자바스크립트 방식으로 직접 쿠키 저장 (시크릿 모드/iframe 차단 대비)
                    # JSON 데이터를 안전하게 문자열화
                    user_info_json = json.dumps(user_info, ensure_ascii=False)
                    import urllib.parse
                    encoded_user_info = urllib.parse.quote(user_info_json)
                    
                    st.components.v1.html(f"""
                        <script>
                            const cookieValue = "{encoded_user_info}";
                            const expires = "{expires.strftime('%a, %d %b %Y %H:%M:%S GMT')}";
                            document.cookie = "{user_key}=" + cookieValue + "; path=/; expires=" + expires + "; SameSite=Lax";
                            // 부모 창에도 시도 (Streamlit 구조 대응)
                            window.parent.document.cookie = "{user_key}=" + cookieValue + "; path=/; expires=" + expires + "; SameSite=Lax";
                        </script>
                    """, height=0)
                    
                    # 시청 목록 및 설정 즉시 로드
                    sync_user_data_to_session(user_info["email"])
                    
                    # 쿠키가 저장될 시간을 아주 잠시 기다린 후 새로고침
                    import time
                    time.sleep(0.5)
                    st.query_params.clear()
                    st.rerun()
            except Exception as e:
                st.error(f"로그인 처리 중 오류 발생: {e}")
        
    # 4. 쿠키 기반 세션 복구 확인 (기존 로그인된 경우)
    user_key = "anime_user_session"
    
    if all_cookies is None:
        # 쿠키 매니저가 아직 로딩 중일 때는 아무것도 하지 않음
        return False
        
    if user_key in all_cookies:
        try:
            import base64
            import urllib.parse
            raw_data = all_cookies[user_key]
            
            # 1. URL 디코딩 (브라우저/라이브러리에 따라 인코딩된 경우 대비)
            if isinstance(raw_data, str) and ("%" in raw_data or "+" in raw_data):
                raw_data = urllib.parse.unquote(raw_data)
            
            # 2. 데이터 파싱 시도 (Base64 -> JSON -> dict 순서)
            user_info = None
            try:
                # Base64 시도
                decoded_str = base64.b64decode(raw_data).decode('utf-8')
                user_info = json.loads(decoded_str)
            except:
                try:
                    # 일반 JSON 시도
                    user_info = json.loads(raw_data)
                except:
                    # 이미 딕셔너리인 경우
                    if isinstance(raw_data, dict):
                        user_info = raw_data
            
            if user_info and isinstance(user_info, dict) and "email" in user_info:
                st.session_state.user_info = user_info
                st.session_state.logged_in = True
                # 쿠키로 복구 시 시청 목록도 함께 로드
                if st.session_state.watched_list is None:
                    try:
                        # 성공 시 데이터 로드
                        sync_user_data_to_session(user_info["email"])
                    except Exception as e:
                        # DB 에러(할당량 등) 발생 시 None으로 유지하여 다음 rerun에 재시도하도록 함
                        st.session_state.watched_list = None
                        st.warning(f"⚠️ 시청 목록을 불러오는 중 오류가 발생했습니다. (잠시 후 자동 재시도)")
                st.rerun() 
        except Exception as e:
            # 복구 실패 시 로그만 남기고 게스트 모드 유지
            pass
    return False

# 보호막 가동
run_auth_shield()

# 6. API 호출 (캐싱)
@st.cache_data(ttl=3600)
def fetch_anime(page, sort, year=None, season=None, genres=None, ex_genres=None, search=None, ids=None, exclude_ids=None, include_adult=False, per_page=24):
    url = 'https://graphql.anilist.co'
    # relations는 상세 정보 로딩 시에만 필요하므로 메인 목록에서는 제외하여 속도 최적화
    media_fields = "id title { native romaji } coverImage { extraLarge } averageScore popularity siteUrl season seasonYear trailer { id site } startDate { year month day } format"
    
    # AniList expects sort to be an array [MediaSort]
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
                st.error(f"API Error: {errors}")
                return None
            return data
        else:
            # 병렬 요청으로 속도 개선 (정상/성인물 동시 조회)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_normal = executor.submit(make_request, False)
                future_adult = executor.submit(make_request, True)
                
                d_normal, e_normal = future_normal.result()
                d_adult, e_adult = future_adult.result()
            
            if e_normal and e_adult:
                st.error(f"API Error: {e_normal}")
                return None
                
            d_normal = d_normal or {}
            d_adult = d_adult or {}
            
            combined_media = d_normal.get('media', []) + d_adult.get('media', [])
            
            # 파이썬 재정렬
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
                "media": combined_media[:24]
            }
    except Exception as e:
        st.error(f"Fetch Error: {e}")
        return None

def fetch_random_anime(year=None, season=None, genres=None, ex_genres=None, search=None, ids=None, exclude_ids=None, include_adult=False):
    """필터에 맞는 작품 중 무작위로 한 페이지를 가져옵니다."""
    # 1. 먼저 전체 페이지 수를 확인하기 위해 1개만 요청
    first_page = fetch_anime(1, "POPULARITY_DESC", year, season, genres, ex_genres, search, ids, exclude_ids, include_adult)
    if not first_page or not first_page.get('media'):
        return None
    
    last_page = first_page['pageInfo']['lastPage']
    # 2. 랜덤 페이지 선택
    random_p = random.randint(1, last_page)
    # 3. 해당 페이지 데이터 가져오기 (캐싱 방지를 위해 sort에 무작위성 가미는 어려우니 순서만 섞음)
    result = fetch_anime(random_p, "POPULARITY_DESC", year, season, genres, ex_genres, search, ids, exclude_ids, include_adult)
    if result and result.get('media'):
        random.shuffle(result['media'])
    return result

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
            
            st.markdown(f'<a href="{st.session_state.google_auth_url}" target="_blank" class="google-login-btn">구글 로그인</a>', unsafe_allow_html=True)
    else:
        st.success(f"**{st.session_state.user_info.get('name')}**님")
        
        
        # --- 시청 통계 섹션 (최적화: 변경 시에만 재계산) ---
        current_watched = st.session_state.watched_list or {}
        watched_count = len(current_watched)
        
        # 캐시 초기화 확인
        if "stats_cache" not in st.session_state:
            st.session_state.stats_cache = {"hash": None, "data": None}
            
        # 현재 시청 목록의 상태를 나타내는 해시 생성 (ID 목록 + 개수)
        current_hash = hash(frozenset(current_watched.keys())) + watched_count
        
        if st.session_state.stats_cache["hash"] != current_hash and watched_count > 0:
            stats_pbar = st.empty()
            with st.spinner("통계 분석 중..."):
                avg_score = sum(v.get('rating', 0) for v in current_watched.values()) / watched_count
                watched_ids = [int(aid) for aid in current_watched.keys()]
                meta_map = get_watched_metadata(watched_ids, p_bar_container=stats_pbar)
                stats_pbar.empty() # 작업 완료 후 표시줄 제거
                
                total_minutes = 0
                genre_stats = {} 
                
                # 시리즈 그룹화 (DSU)
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

                ko_genre_map = {
                    "Action": "액션", "Adventure": "모험", "Comedy": "코미디", "Drama": "드라마", "Ecchi": "에치",
                    "Fantasy": "판타지", "Horror": "공포", "Mahou Shoujo": "마법소녀", "Mecha": "메카", 
                    "Music": "음악", "Mystery": "미스터리", "Psychological": "심리", "Romance": "로맨스", 
                    "Sci-Fi": "SF", "Slice of Life": "일상", "Sports": "스포츠", "Supernatural": "초자연", "Thriller": "스릴러"
                }

                for aid, info in current_watched.items():
                    meta = meta_map.get(aid)
                    rating = info.get('rating', 0)
                    if meta:
                        count = info.get('count', 1)
                        total_minutes += meta['episodes'] * meta['duration'] * count
                        for g in meta['genres']:
                            ko_g = ko_genre_map.get(g, g)
                            if ko_g not in genre_stats: genre_stats[ko_g] = [0, 0]
                            genre_stats[ko_g][0] += rating
                            genre_stats[ko_g][1] += 1
                
                sorted_genres = sorted(genre_stats.items(), key=lambda x: x[1][1], reverse=True)
                
                # 시간 포맷팅
                if total_minutes >= 1440:
                    days = total_minutes // 1440
                    hours = (total_minutes % 1440) // 60
                    t_str = f"{days}일 {hours}시간"
                elif total_minutes >= 60:
                    hours = total_minutes // 60
                    mins = total_minutes % 60
                    t_str = f"{hours}시간 {mins}분"
                else:
                    t_str = f"{total_minutes}분"
                    
                # 결과 캐싱 (원천 데이터인 total_minutes를 함께 저장)
                st.session_state.stats_cache = {
                    "hash": current_hash,
                    "data": {
                        "avg_score": avg_score,
                        "series_count": series_count,
                        "total_minutes": total_minutes,
                        "sorted_genres": sorted_genres
                    }
                }

        # 캐시된 데이터 사용
        stats = st.session_state.stats_cache["data"] or {
            "avg_score": 0, "series_count": 0, "total_minutes": 0, "sorted_genres": []
        }
        avg_score = stats["avg_score"]
        series_count = stats["series_count"]
        total_minutes = stats["total_minutes"]
        sorted_genres = stats["sorted_genres"]

        # 1. 시청 시간 단위 설정 (팝오버로 분리하여 레이아웃 깨짐 방지)
        st.write("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col_title, col_opt = st.columns([3, 1])
        with col_title:
            st.markdown('<div style="font-size: 0.9rem; font-weight: bold; margin-top: 5px;">📊 나의 아카이브 현황</div>', unsafe_allow_html=True)
        with col_opt:
            with st.popover("⚙️", help="시청 시간 단위 변경"):
                t_unit = st.selectbox("시간 단위", ["일", "시간", "분", "초"], 
                                    index=["일", "시간", "분", "초"].index(st.session_state.time_unit), 
                                    key="time_unit_selector")
                if t_unit != st.session_state.time_unit:
                    st.session_state.time_unit = t_unit
                    update_user_setting("time_unit", t_unit)

        # 2. 시간 포맷팅 계산
        if st.session_state.time_unit == "일": total_time_str = f"{total_minutes / 1440:.1f}일"
        elif st.session_state.time_unit == "시간": total_time_str = f"{total_minutes / 60:.1f}시간"
        elif st.session_state.time_unit == "분": total_time_str = f"{total_minutes:,}분"
        elif st.session_state.time_unit == "초": total_time_str = f"{total_minutes * 60:,}초"
        else: total_time_str = f"{total_minutes / 60:.1f}시간" # Fallback to hours

        # 3. 통합 통계 카드 (단일 마크다운으로 구성하여 절대 깨지지 않음)
        st.markdown(f"""
        <div style="background: rgba(76, 175, 80, 0.1); padding: 15px; border-radius: 12px; border: 1px solid rgba(76, 175, 80, 0.2); margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-around; align-items: center; text-align: center; margin-bottom: 15px;">
                <div>
                    <div style="font-size: 1.2rem; font-weight: bold; color: #4CAF50;">{watched_count}</div>
                    <div style="font-size: 0.65rem; color: var(--secondary-text-color);">시청 작품</div>
                </div>
                <div style="border-left: 1px solid rgba(76, 175, 80, 0.2); height: 30px;"></div>
                <div>
                    <div style="font-size: 1.2rem; font-weight: bold; color: #2E7D32;">{series_count}</div>
                    <div style="font-size: 0.65rem; color: var(--secondary-text-color);">시리즈</div>
                </div>
                <div style="border-left: 1px solid rgba(76, 175, 80, 0.2); height: 30px;"></div>
                <div>
                    <div style="font-size: 1.2rem; font-weight: bold; color: #f39c12;">{avg_score:.1f}</div>
                    <div style="font-size: 0.65rem; color: var(--secondary-text-color);">평균 평점</div>
                </div>
            </div>
            <div style="border-top: 1px dashed rgba(76, 175, 80, 0.2); padding-top: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 0.8rem; font-weight: bold; color: var(--text-color);">총 시청 시간</div>
                    <div style="font-size: 0.6rem; color: #666; background: rgba(0,0,0,0.05); padding: 1px 5px; border-radius: 4px;">{st.session_state.time_unit}</div>
                </div>
                <div style="font-size: 1.15rem; color: #4CAF50; font-weight: bold; margin-top: 5px;">⏱️ {total_time_str}</div>
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
                            <span style="color: #f39c12; font-size: 0.85rem; margin-left: 8px;">★ {g_avg:.1f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("데이터가 없습니다.")

        # --- 데이터 내보내기/가져오기 섹션 ---
        with st.expander("💾 데이터 내보내기/가져오기"):
            # 1. 내보내기 (Export)
            if watched_count > 0:
                # JSON 직렬화 가능한 형태로 변환 (제목 포함)
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
            
            # 2. 가져오기 (Import)
            uploaded_file = st.file_uploader("JSON 파일 가져오기", type=["json"], help="기존에 내보낸 JSON 파일을 업로드하세요.")
            if uploaded_file:
                try:
                    import_data = json.load(uploaded_file)
                    if st.button("🚀 데이터 병합 및 업로드", use_container_width=True, type="primary"):
                        # 유효성 검사 및 정규화
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
                            # 현재 세션 상태와 병합
                            if st.session_state.watched_list is None:
                                st.session_state.watched_list = {}
                            
                            # 병합 (가져온 데이터가 우선)
                            st.session_state.watched_list.update(valid_data)
                            
                            # Firebase에 업데이트 (병합된 전체 목록 전송)
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
                # 1. URL 파라미터에 logout=true 설정 (새로고침 대비)
                st.query_params["logout"] = "true"
                
                # 2. 쿠키 삭제 (새로운 이름 적용 및 안전한 삭제)
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

                # 3. 세션 상태 초기화
                st.session_state.logged_in = False
                st.session_state.user_info = None
                st.session_state.watched_list = {}
                st.session_state.logout_clicked = True
                
                st.success("로그아웃 되었습니다.")
                st.rerun()

    st.divider()
    st.header("🔍 검색 및 필터")
    
    # 제목 검색 (즉시 반영)
    search_q = st.query_params.get("q", "")
    
    # 1. '이름으로 검색' 버튼 등으로 URL이 외부에서 바뀌었을 때만 위젯 상태 동기화
    if "prev_q" not in st.session_state:
        st.session_state.prev_q = search_q
        
    if search_q != st.session_state.prev_q:
        st.session_state.search_input = search_q
        st.session_state.prev_q = search_q
        
    # 2. 위젯 생성 (value 인자 제거하여 세션 상태와 충돌 방지)
    new_search = st.text_input("제목 검색", placeholder="영문 또는 일문 제목", key="search_input")

    # 모바일 키보드 제어 JS (검색창은 키보드 활성화, 필터류는 비활성화)
    st.components.v1.html("""
        <script>
            function setupInputs() {
                const doc = window.parent.document;
                const inputs = doc.querySelectorAll('input');
                
                inputs.forEach(input => {
                    // 1. 제목 검색창: 키보드 '검색' 버튼 설정
                    if (input.placeholder === "영문 또는 일문 제목") {
                        input.type = "search";
                        input.setAttribute("enterkeyhint", "search");
                        input.addEventListener("keydown", (e) => {
                            if (e.key === "Enter") input.blur();
                        });
                    }
                    
                    // 2. 필터류 (년도, 분기, 장르, 시청여부): 키보드 팝업 및 커서 방지
                    const container = input.closest('div[data-testid="stSelectbox"], div[data-testid="stMultiSelect"]');
                    if (container) {
                        const label = container.querySelector('label');
                        if (label && ["년도", "분기", "포함 장르", "제외 장르", "시청 여부", "시간 단위"].some(text => label.textContent.trim() === text)) {
                            // inputmode="none"은 모바일 키보드를 띄우지 않게 함
                            input.setAttribute('inputmode', 'none');
                            // readonly는 텍스트 입력을 막고 커서(I-beam)가 생기는 것을 방지함
                            input.setAttribute('readonly', 'true');
                            input.style.cursor = 'pointer';
                        }
                    }
                });
            }

            // Streamlit의 렌더링 타이밍을 고려하여 지연 실행 및 반복 실행
            setTimeout(setupInputs, 500);
            setTimeout(setupInputs, 1500);
            setTimeout(setupInputs, 2500);
        </script>
    """, height=0)

    if new_search != search_q:
        st.query_params["q"] = new_search
        st.session_state.prev_q = new_search # 변경된 값을 즉시 반영하여 역동기화 방지
        st.session_state.page = 1
        st.rerun()

    st.divider()
    years = ["전체"] + list(range(datetime.now().year, 1989, -1))
    s_year_val = st.selectbox("년도", years)
    s_year = s_year_val if s_year_val != "전체" else None

    season_labels = ["전체", "1분기", "2분기", "3분기", "4분기"]
    season_values = [None, "WINTER", "SPRING", "SUMMER", "FALL"]
    season_map = dict(zip(season_labels, season_values))
    
    s_season_label = st.selectbox("분기", season_labels)
    s_season = season_map[s_season_label]
    
    # 장르 선택
    genre_map = {
        "액션": "Action", "모험": "Adventure", "코미디": "Comedy", "드라마": "Drama", "에치": "Ecchi",
        "판타지": "Fantasy", "공포": "Horror", "마법소녀": "Mahou Shoujo", "메카": "Mecha", 
        "음악": "Music", "미스터리": "Mystery", "심리": "Psychological", "로맨스": "Romance", 
        "SF": "Sci-Fi", "일상": "Slice of Life", "스포츠": "Sports", "초자연": "Supernatural", "스릴러": "Thriller"
    }
    selected_genres = st.multiselect("포함 장르", list(genre_map.keys()))
    s_genres = [genre_map[g] for g in selected_genres] if selected_genres else None

    # 제외 장르 추가 (-)
    excluded_genres = st.multiselect("제외 장르", list(genre_map.keys()))
    s_ex_genres = [genre_map[g] for g in excluded_genres] if excluded_genres else None
    
    # 시청 여부 필터 (Mutual Exclusive)
    watch_options = ["전체", "본 작품만", "안 본 작품만"]
    s_watch = st.selectbox("시청 여부", watch_options) if st.session_state.logged_in else "전체"
    only_w = (s_watch == "본 작품만")
    only_not_w = (s_watch == "안 본 작품만")
    
    # 성인물 설정 (쿼리 파라미터 연동으로 새로고침 유지)
    adult_param = st.query_params.get("adult", "false") == "true"
    s_adult = st.checkbox("성인물 포함", value=adult_param)

    if s_adult != adult_param:
        st.query_params["adult"] = "true" if s_adult else "false"
        st.session_state.page = 1
        st.rerun()
    
    # 내 평점 필터 추가 (봤을 때만 유효)
    s_rating = 0.0
    if only_w:
        s_rating = st.slider("최소 평점 (내 평점)", 0.0, 5.0, 0.0, 0.1)

    st.divider()
    if st.button("🎲 랜덤 추천 받기", use_container_width=True, type="primary"):
        with st.spinner("랜덤 작품 찾는 중..."):
            # 필터링 조건 정리
            target_ids = None
            exclude_ids = None
            current_watched = st.session_state.watched_list or {}
            
            if only_w:
                target_ids = [aid for aid, info in current_watched.items() if info.get('rating', 0) >= s_rating]
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
            st.session_state.all_media = [] # 목록 초기화하여 1페이지부터 다시 로드
            st.rerun()

# 정렬 옵션 설정
sort_map = {"인기도순": "POPULARITY_DESC", "평점순": "SCORE_DESC", "방영일순": "START_DATE_DESC"}
if st.session_state.logged_in and only_w:
    sort_map["내 평점순"] = "MY_SCORE_DESC"
else:
    # "내 평점순"이 선택된 상태에서 필터가 바뀌어 더 이상 유효하지 않은 경우 정렬 초기화
    if st.session_state.sort_by == "내 평점순":
        st.session_state.sort_by = "인기도순"

# 필터 상태 감지 (변경 시 목록 초기화)
current_filters = {
    "q": new_search, "y": s_year, "s": s_season, 
    "g": str(s_genres), "eg": str(s_ex_genres),
    "only_w": only_w, "only_not_w": only_not_w, "adult": s_adult, "rating": s_rating,
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

# 데이터 로드 (필요할 때만)
if st.session_state.has_next and (not st.session_state.all_media or len(st.session_state.all_media) < st.session_state.page * 24):
    target_ids = None
    exclude_ids = None
    
    # 1. 시청한 작품 필터링 및 정렬용 ID 목록 생성
    current_watched = st.session_state.watched_list or {}
    if only_w:
        target_ids = [aid for aid, info in current_watched.items() if info.get('rating', 0) >= s_rating]
        
        # "내 평점순"인 경우 ID 목록 자체를 평점순(1순위) + 시청 횟수순(2순위)으로 미리 정렬
        if st.session_state.sort_by == "내 평점순":
            target_ids.sort(key=lambda aid: (
                current_watched[aid].get('rating', 0), 
                current_watched[aid].get('count', 1)
            ), reverse=True)
            
        if not target_ids: 
            target_ids = [0]
        else:
            # AniList id_in limit (일반적으로 500개)
            target_ids = target_ids[:500]
    
    if only_not_w:
        exclude_ids = list(current_watched.keys())
        if exclude_ids:
            exclude_ids = exclude_ids[:500]

    # API용 정렬 값 결정
    api_sort = sort_map.get(st.session_state.sort_by, "POPULARITY_DESC")
    
    # "내 평점순" 정렬 로직 (전체 데이터를 평점순으로 정렬 후 페이징)
    is_my_rating_sort = (st.session_state.sort_by == "내 평점순" and only_w)
    
    if is_my_rating_sort:
        # 1. 정렬된 ID 리스트를 기준으로 현재 페이지에 필요한 ID들만 추출
        per_page = 24
        start_idx = (st.session_state.page - 1) * per_page
        end_idx = start_idx + per_page
        
        # target_ids는 이미 위에서 평점순으로 정렬됨
        paged_ids = target_ids[start_idx:end_idx]
        
        if paged_ids:
            # 2. 해당 ID들에 대한 정보만 API에서 가져옴
            data = fetch_anime(
                1, "POPULARITY_DESC", # 순서는 paged_ids로 강제할 것임
                s_year, s_season, s_genres, s_ex_genres,
                new_search if new_search else None,
                ids=paged_ids,
                exclude_ids=exclude_ids,
                include_adult=s_adult
            )
            
            if data and data['media']:
                new_items = data['media']
                # 3. API는 순서를 보장하지 않으므로 paged_ids 순서대로 다시 재배치 (핵심!)
                media_dict = {m['id']: m for m in new_items}
                sorted_new_items = []
                for aid in paged_ids:
                    if aid in media_dict:
                        sorted_new_items.append(media_dict[aid])
                
                # 4. 세션 목록에 추가 (중복 방지)
                existing_ids = {m['id'] for m in st.session_state.all_media}
                for item in sorted_new_items:
                    if item['id'] not in existing_ids:
                        st.session_state.all_media.append(item)
                
                # 페이징 정보 갱신
                st.session_state.has_next = end_idx < len(target_ids)
                st.session_state.total_pages = (len(target_ids) + per_page - 1) // per_page
    else:
        # 일반적인 API 페이징 처리 (루프를 통해 부족한 수량 채움)
        if api_sort == "MY_SCORE_DESC": api_sort = "POPULARITY_DESC"
        
        # 목표 수량이 채워질 때까지 최대 5번 시도 (무한 루프 방지)
        attempts = 0
        while st.session_state.has_next and len(st.session_state.all_media) < st.session_state.page * 24 and attempts < 5:
            attempts += 1
            # 안 본 작품만 필터링 시에는 한 번에 50개씩 가져와서 효율성 증대
            fetch_size = 50 if only_not_w else 24
            
            data = fetch_anime(
                st.session_state.api_page, 
                api_sort, 
                s_year, s_season, s_genres, s_ex_genres,
                new_search if new_search else None,
                ids=target_ids,
                exclude_ids=exclude_ids,
                include_adult=s_adult,
                per_page=fetch_size
            )

            if data:
                new_items = data['media']
                
                # "안 본 작품만" 필터링 시 클라이언트 사이드에서 한 번 더 검증 (500개 제한 대비)
                current_watched = st.session_state.watched_list or {}
                if only_not_w:
                    new_items = [m for m in new_items if m['id'] not in current_watched]
                
                # "내 평점순"인 경우 가져온 결과 내에서 다시 한 번 정렬 (평점 -> 시청 횟수 순)
                if st.session_state.sort_by == "내 평점순":
                    new_items.sort(key=lambda x: (
                        current_watched.get(x['id'], {}).get('rating', 0),
                        current_watched.get(x['id'], {}).get('count', 1)
                    ), reverse=True)
                
                # 중복 제거 및 추가
                existing_ids = {m['id'] for m in st.session_state.all_media}
                added_count = 0
                for item in new_items:
                    if item['id'] not in existing_ids:
                        st.session_state.all_media.append(item)
                        added_count += 1
                
                st.session_state.has_next = data['pageInfo']['hasNextPage']
                st.session_state.total_pages = data['pageInfo']['lastPage']
                st.session_state.api_page += 1
                
                # 만약 이번 페이지에서 아무것도 추가되지 않았는데 다음 페이지가 있다면 즉시 다음 시도
                if added_count == 0 and st.session_state.has_next:
                    continue
                else:
                    break
            else:
                break

# 7. 메인 화면 렌더링
anime_list = st.session_state.all_media
total_loaded = len(anime_list)

# 상단 헤더 및 정렬 UI
h_col1, h_col2 = st.columns([4, 1])
with h_col1:
    if st.session_state.is_random_mode:
        st.title(f"🎲 랜덤 추천 결과 ({total_loaded}개)")
    elif new_search:
        st.title(f"🔍 '{new_search}' 검색 결과 ({total_loaded}개)")
    else:
        title_parts = [] 
        if s_year: title_parts.append(str(s_year))
        if s_season_label != "전체": title_parts.append(s_season_label)
        title_text = " ".join(title_parts) if title_parts else "전체 목록"
        st.title(f"📅 {title_text} Archive ({total_loaded}개)")
with h_col2:
    st.write("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    if not st.session_state.is_random_mode:
        st.selectbox("정렬 방식", list(sort_map.keys()), key="sort_by", label_visibility="collapsed")

st.divider()

if not anime_list: 
    st.info("데이터가 없습니다.")
else:
    # 4개씩 묶어서 행(row) 단위로 렌더링 (모바일 정렬 순서 문제 해결)
    for i in range(0, len(anime_list), 4):
        cols = st.columns(4)
        chunk = anime_list[i:i+4]
        for j, anime in enumerate(chunk):
            a_id = anime['id']
            current_watched = st.session_state.watched_list or {}
            with cols[j]:
                st.markdown('<div class="anime-card-container">', unsafe_allow_html=True)
                st.image(anime['coverImage']['extraLarge'], use_container_width=True)
                is_w = a_id in current_watched
                if is_w:
                    w_data = current_watched.get(a_id, {})
                    user_rating = w_data.get("rating", 5.0)
                    user_count = w_data.get("count", 1)
                    count_str = f" ({user_count}회)" if user_count > 1 else ""
                    st.markdown(f'<div class="watched-badge">✓ {user_rating}점{count_str}</div>', unsafe_allow_html=True)
                else: st.markdown('<div style="height:1.5rem; margin-bottom:5px;"></div>', unsafe_allow_html=True)

                st.markdown(f"<div class='anime-title-box'>{anime['title']['native'] or anime['title']['romaji']}</div>", unsafe_allow_html=True)
                
                # 포맷 매핑
                f_map = {
                    "TV": "TV", "TV_SHORT": "TV (Short)", "MOVIE": "영화", 
                    "SPECIAL": "특별편", "OVA": "OVA", "ONA": "ONA", "MUSIC": "뮤직"
                }
                a_format = f_map.get(anime.get('format'), anime.get('format') or "Unknown")
                st.markdown(f"<div style='font-size: 0.75rem; color: #888; margin-top: -10px; margin-bottom: 5px;'>{a_format}</div>", unsafe_allow_html=True)

                s_map = {"WINTER": "1분기", "SPRING": "2분기", "SUMMER": "3분기", "FALL": "4분기"}
                a_year = anime.get('seasonYear') or "미정"
                a_season = s_map.get(anime.get('season'), "")
                st.markdown(f"<div class='anime-info-box'>📅 {a_year}년 {a_season}</div>", unsafe_allow_html=True)

                raw_score = anime.get('averageScore')
                if raw_score:
                    score_5 = round(raw_score / 20, 1)
                    full_stars = int(score_5)
                    stars = "★" * full_stars + "☆" * (5 - full_stars)
                    score_html = f"<div class='score-box'>{stars} {score_5}</div>"
                else:
                    score_html = "<div class='score-box' style='color:#bbb;'>☆☆☆☆☆ 0.0</div>"

                st.markdown(score_html, unsafe_allow_html=True)

                if is_w:
                    w_data = current_watched.get(a_id, {})
                    user_comment = w_data.get("comment", "")
                    if user_comment:
                        st.markdown(f'<div class="user-comment-box">"{user_comment}"</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="empty-comment-box"></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="empty-comment-box"></div>', unsafe_allow_html=True)

                c1, c2, c3 = st.columns(3, gap="small")
                
                # 상세 팝오버
                with c1.popover("상세", use_container_width=True, key=f"pop_detail_{a_id}"):
                    st.link_button("AniList에서 보기", anime['siteUrl'], use_container_width=True)
                    
                    st.divider()
                    if st.button("🔍 이름으로 검색", key=f"btn_search_{a_id}", use_container_width=True, type="primary"):
                        title = anime['title']['native'] or anime['title']['romaji']
                        # URL 파라미터만 갱신 (위젯 상태는 다음 런의 최상단 동기화 로직에서 처리)
                        st.query_params["q"] = title
                        # 목록 초기화 및 페이지 리셋
                        st.session_state.all_media = []
                        st.session_state.page = 1
                        st.rerun()
                
                # 예고편 버튼
                trailer = anime.get('trailer')
                if trailer and trailer.get('site') == 'youtube':
                    with c2.popover("🎬", use_container_width=True, key=f"trailer_{a_id}"):
                        st.video(f"https://www.youtube.com/watch?v={trailer['id']}")
                else:
                    c2.button("🎬", disabled=True, use_container_width=True, help="예고편 정보가 없습니다.", key=f"no_trailer_{a_id}")

                if st.session_state.logged_in:
                    # action_cnt를 모든 위젯 키에 반영하여 동작 후 확실하게 창이 닫히고 초기화되도록 함
                    ac = st.session_state.action_cnt
                    pop_label = "수정" if is_w else "시청"
                    
                    with c3.popover(pop_label, use_container_width=True, key=f"pop_act_{a_id}_{ac}"):
                        if is_w:
                            w_data = current_watched.get(a_id, {})
                            u_score = st.slider("내 평점", 0.0, 5.0, round(float(w_data.get("rating", 5.0)), 1), 0.1, format="%.1f", key=f"score_edit_{a_id}_{ac}")
                            u_count = st.number_input("시청 횟수", min_value=1, value=int(w_data.get("count", 1)), step=1, key=f"count_edit_{a_id}_{ac}")
                            u_comment = st.text_area("코멘트", value=w_data.get("comment", ""), placeholder="짧은 감상평을 남겨주세요", key=f"comm_edit_{a_id}_{ac}")
                            
                            if st.button("업데이트", key=f"btn_update_{a_id}_{ac}", use_container_width=True, type="primary"):
                                # 낙관적 업데이트: UI에 즉시 반영
                                if st.session_state.watched_list is None: st.session_state.watched_list = {}
                                st.session_state.watched_list[a_id] = {"rating": u_score, "comment": u_comment, "count": u_count}
                                # 백그라운드 저장 시동
                                update_db(a_id, "add", u_score, u_comment, u_count)
                                st.session_state.action_cnt += 1
                                st.rerun()
                                
                            st.divider()
                            if st.button("시청 기록 삭제", key=f"btn_delete_{a_id}_{ac}", use_container_width=True):
                                # 낙관적 삭제
                                if st.session_state.watched_list is not None:
                                    st.session_state.watched_list.pop(a_id, None)
                                update_db(a_id, "remove")
                                st.session_state.action_cnt += 1
                                st.rerun()
                        else:
                            u_score = st.slider("내 평점", 0.0, 5.0, 5.0, 0.1, key=f"score_new_{a_id}_{ac}")
                            u_count = st.number_input("시청 횟수", min_value=1, value=1, step=1, key=f"count_new_{a_id}_{ac}")
                            u_comment = st.text_area("코멘트", placeholder="짧은 감상평을 남겨주세요", key=f"comm_new_{a_id}_{ac}")
                            
                            if st.button("저장", key=f"btn_save_{a_id}_{ac}", use_container_width=True, type="primary"):
                                # 낙관적 저장
                                if st.session_state.watched_list is None: st.session_state.watched_list = {}
                                st.session_state.watched_list[a_id] = {"rating": u_score, "comment": u_comment, "count": u_count}
                                update_db(a_id, "add", u_score, u_comment, u_count)
                                st.session_state.action_cnt += 1
                                st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            st.write("") 

    # 하단 네비게이션 로직 (수동 로딩)
    st.write("---")
    if st.session_state.is_random_mode:
        if st.button("🎲 랜덤 작품 더 보기", use_container_width=True):
            with st.spinner("새로운 랜덤 작품 찾는 중..."):
                # 필터링 조건 정리
                target_ids = None
                exclude_ids = None
                current_watched = st.session_state.watched_list or {}
                
                if only_w:
                    target_ids = [aid for aid, info in current_watched.items() if info.get('rating', 0) >= s_rating]
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
                    # 중복 제거하며 추가
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
